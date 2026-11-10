from collections import Counter

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import UsuarioAutenticado, require_admin
from app.database import get_db
from app.models import Assinatura
from app.openapi_responses import RESP_401, RESP_403_ADMIN, RESP_502_AUTH_SERVICE, RESP_502_LOG_SERVICE
from app.services import log_client, pagamentos
from app.services.auth_client import AuthServiceUnavailable, forward

router = APIRouter(prefix="/admin", tags=["admin"])

_RESP_ADMIN = RESP_401 | RESP_403_ADMIN

# Ordem dos planos no painel (papel do RBAC = plano).
PAPEIS = ("professor", "professor_pro", "coordenador", "admin")


class ResumoAdminOut(BaseModel):
    usuarios_por_plano: dict[str, int] = Field(
        description="Quantos usuários há em cada papel/plano (professor = Free, professor_pro = Pro, "
        "coordenador = Escola, admin)"
    )
    total_usuarios: int
    assinaturas_ativas: int = Field(description="Assinaturas do Stripe com status pagante (active/trialing)")
    assinaturas_ativas_por_plano: dict[str, int]
    inadimplentes: int = Field(description="Assinaturas com pagamento recusado (past_due/unpaid)")
    mrr_centavos: int = Field(
        description="MRR de teste: soma do valor mensal das assinaturas ativas, em centavos de real"
    )
    eventos_recentes: list[dict] = Field(description="Os 10 eventos de auditoria mais recentes (vazio se o log-service cair)")


@router.get("/resumo", response_model=ResumoAdminOut, responses=_RESP_ADMIN | RESP_502_AUTH_SERVICE)
def resumo(
    authorization: str | None = Header(None),
    _usuario_atual: UsuarioAutenticado = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ResumoAdminOut:
    """Só admin: a saúde do negócio numa tela (atividade 11) — usuários por
    plano, assinaturas ativas, MRR do modo de teste e os últimos eventos.

    Os usuários vêm do auth-service (dono da tabela `usuarios`), repassando
    o mesmo header Authorization; as assinaturas, da tabela `assinaturas`,
    que os webhooks do Stripe mantêm em dia."""
    try:
        resposta = forward("GET", "/auth/admin/users", headers={"Authorization": authorization or ""})
    except AuthServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    if resposta.status_code != 200:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Não foi possível listar os usuários")
    papeis = Counter(u.get("role") for u in resposta.json())

    ativas = [
        a
        for a in db.query(Assinatura).filter(Assinatura.premium.is_(True)).all()
        if (a.status or "active") in pagamentos.STATUS_PAGANTES
    ]
    inadimplentes = db.query(Assinatura).filter(Assinatura.status.in_(("past_due", "unpaid"))).count()

    eventos: list[dict] = []
    try:
        resposta_log = log_client.consultar_eventos(10, authorization)
        if resposta_log.status_code == 200:
            eventos = resposta_log.json()
    except log_client.LogServiceUnavailable:
        pass

    return ResumoAdminOut(
        usuarios_por_plano={papel: papeis.get(papel, 0) for papel in PAPEIS},
        total_usuarios=sum(papeis.values()),
        assinaturas_ativas=len(ativas),
        assinaturas_ativas_por_plano=dict(Counter(a.plano for a in ativas)),
        inadimplentes=inadimplentes,
        # Assinatura antiga (atividade 7) não tem o valor no banco: usa o
        # preço atual do plano no Stripe.
        mrr_centavos=sum(
            a.valor_mensal_centavos
            if a.valor_mensal_centavos is not None
            else (pagamentos.valor_mensal_do_plano(a.plano) or 0)
            for a in ativas
        ),
        eventos_recentes=eventos,
    )


@router.get("/logs", responses=_RESP_ADMIN | RESP_502_LOG_SERVICE)
def consultar_logs(
    limit: int = Query(50, ge=1, le=1000),
    authorization: str | None = Header(None),
    _usuario_atual: UsuarioAutenticado = Depends(require_admin),
) -> JSONResponse:
    """Só admin: consulta os últimos N eventos de auditoria (atividade 5).

    Log-service não tem porta publicada pro host (mesmo princípio do
    auth-service), então essa rota é a única forma de um admin consultar o
    log de fora — o catálogo já barra com 403 quem não for admin
    (`require_admin`, mesmo enforcement da atividade 4) e repassa o header
    Authorization original pro log-service, que confere de novo com o
    mesmo JWT: defesa em profundidade, não round-trip redundante à toa."""
    try:
        resposta = log_client.consultar_eventos(limit, authorization)
    except log_client.LogServiceUnavailable as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    return JSONResponse(status_code=resposta.status_code, content=resposta.json())
