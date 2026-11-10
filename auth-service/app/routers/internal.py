from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.security import decode_service_token
from app.config import get_settings
from app.database import get_db
from app.models import Usuario
from app.models.usuario import PAPEIS_VALIDOS
from app.schemas.auth import UsuarioOut
from app.services.mailer import send_payment_failed_email

# Rotas só pra outros serviços, nunca pro navegador: o auth-service não tem
# porta publicada e o catálogo não repassa nada de /internal pra fora.
router = APIRouter(prefix="/internal", tags=["internal"])


class PapelPagoIn(BaseModel):
    role: str


class AvisoPagamentoIn(BaseModel):
    plano: str | None = None


def require_servico_catalogo(authorization: str | None = Header(None)) -> None:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token or decode_service_token(token) is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token de serviço inválido")


@router.put(
    "/users/{usuario_id}/role",
    response_model=UsuarioOut,
    dependencies=[Depends(require_servico_catalogo)],
)
def definir_papel_pago(
    usuario_id: int, dados: PapelPagoIn, db: Session = Depends(get_db)
) -> UsuarioOut:
    """Plano pago (atividade 7): o webhook do Stripe chega no catálogo, que
    confirma a assinatura e pede aqui a troca do papel — quem é dono da
    tabela `usuarios` continua sendo só o auth-service.

    Admin nunca é rebaixado por plano (nem por cancelamento): o papel dele
    não veio de pagamento."""
    if dados.role not in PAPEIS_VALIDOS or dados.role == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Papel inválido para plano")
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    if usuario.role != "admin":
        usuario.role = dados.role
        db.commit()
        db.refresh(usuario)
    return usuario


@router.post(
    "/users/{usuario_id}/aviso-pagamento-recusado",
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_servico_catalogo)],
)
def avisar_pagamento_recusado(
    usuario_id: int,
    dados: AvisoPagamentoIn,
    tarefas: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Atividade 11: o catálogo recebeu `invoice.payment_failed` do Stripe e
    pede o e-mail de aviso. O e-mail mora aqui (tabela `usuarios`), então é
    o auth-service quem envia — em segundo plano, pra não segurar o webhook."""
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
    link = f"{get_settings().catalog_public_url}/app/planos"
    tarefas.add_task(send_payment_failed_email, usuario.email, usuario.nome, dados.plano, link)
    return {"aviso": "enviando"}
