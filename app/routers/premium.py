import json
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.dependencies import NIVEL_PAPEL, UsuarioAutenticado, get_current_user
from app.database import get_db
from app.models import Assinatura
from app.openapi_responses import (
    RESP_401,
    RESP_409_PLANO,
    RESP_502_AUTH_SERVICE,
    RESP_ERROS_PAGAMENTO,
    RESP_ERROS_WEBHOOK,
)
from app.services import log_client, pagamentos
from app.services.auth_client import PapelNaoAtualizado, definir_papel_pago

router = APIRouter(prefix="/premium", tags=["premium"])

# Plano gratuito: é pra ele que volta quem cancela um plano pago.
PLANO_GRATUITO = "professor"


class CheckoutIn(BaseModel):
    # Free (professor) não é vendido (é o gratuito); admin não é plano.
    plano: Literal["professor_pro", "coordenador"]


class CheckoutOut(BaseModel):
    checkout_url: str


class StatusPremiumOut(BaseModel):
    premium: bool
    # Plano pago ativo (professor_pro / coordenador), ou None no gratuito.
    plano: str | None


def plano_pago(db: Session, usuario_id: int) -> str | None:
    assinatura = db.get(Assinatura, usuario_id)
    return assinatura.plano if assinatura is not None and assinatura.premium else None


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    responses=RESP_401 | RESP_409_PLANO | RESP_ERROS_PAGAMENTO,
)
def criar_checkout(
    dados: CheckoutIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
) -> CheckoutOut:
    """Abre o pagamento do plano escolhido no Stripe e devolve a URL dele.

    Devolve a URL em vez de um 302 porque o front é uma SPA que se
    autentica por header (Bearer), não por cookie: um redirect do servidor
    não levaria o token. O front recebe a URL e faz o redirecionamento.

    Só deixa comprar um plano ACIMA do papel atual — comprar o mesmo ou um
    abaixo não daria nada a mais (admin já tem tudo)."""
    if NIVEL_PAPEL.get(usuario_atual.role, 0) >= NIVEL_PAPEL[dados.plano]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Você já tem esse plano ou um superior"
        )
    try:
        url = pagamentos.criar_checkout(usuario_atual.id, dados.plano)
    except pagamentos.PagamentoNaoConfigurado as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    except pagamentos.PagamentoIndisponivel as erro:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro
    log_client.registrar_evento(
        usuario_atual.id,
        f"abrir_checkout:{dados.plano}",
        ip=request.client.host if request.client else None,
    )
    return CheckoutOut(checkout_url=url)


@router.get("/status", response_model=StatusPremiumOut, responses=RESP_401)
def status_premium(
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatusPremiumOut:
    """O front consulta isso na volta do checkout: a confirmação do
    pagamento chega por outro caminho (webhook), e pode chegar depois do
    navegador voltar — então ele pergunta até o plano aparecer."""
    plano = plano_pago(db, usuario_atual.id)
    return StatusPremiumOut(premium=plano is not None, plano=plano)


def _trocar_papel(usuario_id: int, papel: str) -> None:
    try:
        definir_papel_pago(usuario_id, papel)
    except PapelNaoAtualizado as erro:
        # Erro de propósito: sem 2xx, o Stripe reenvia o evento mais tarde
        # (e processar de novo dá no mesmo) — o pagamento não se perde.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro


def _ativar_plano(db: Session, sessao: dict) -> None:
    """checkout.session.completed: o pagamento foi concluído. Quem pagou
    vem do `client_reference_id` e o plano do `metadata` — os dois postos
    pelo próprio catálogo na sessão e devolvidos intactos pelo Stripe."""
    plano = (sessao.get("metadata") or {}).get("plano")
    if (
        sessao.get("mode") != "subscription"
        or not sessao.get("client_reference_id")
        or plano not in pagamentos.PLANOS_PAGOS
    ):
        return
    usuario_id = int(sessao["client_reference_id"])

    # Primeiro o papel (no auth-service); só depois grava a assinatura. Se
    # o auth-service falhar, nada foi gravado e o reenvio do Stripe refaz tudo.
    _trocar_papel(usuario_id, plano)

    assinatura = db.get(Assinatura, usuario_id)
    if assinatura is None:
        assinatura = Assinatura(usuario_id=usuario_id)
        db.add(assinatura)
    assinatura_antiga = assinatura.stripe_subscription_id
    # Idempotente: o Stripe reenvia o mesmo evento se não receber 2xx a
    # tempo — processar duas vezes dá no mesmo resultado.
    assinatura.premium = True
    assinatura.plano = plano
    assinatura.stripe_customer_id = sessao.get("customer")
    assinatura.stripe_subscription_id = sessao.get("subscription")
    db.commit()

    # Trocou de plano (ex.: Pro -> Escola): cancela a assinatura anterior.
    # O cancelamento dispara outro webhook, mas ele não acha mais essa
    # assinatura no banco (o ID já é o novo) — então não rebaixa ninguém.
    if assinatura_antiga and assinatura_antiga != assinatura.stripe_subscription_id:
        pagamentos.cancelar_assinatura(assinatura_antiga)
    log_client.registrar_evento(usuario_id, f"plano_ativado:{plano}")


def _encerrar_plano(db: Session, assinatura_stripe: dict) -> None:
    """customer.subscription.deleted: a assinatura acabou (cancelada no
    painel do Stripe, ou cobrança recusada até esgotar as tentativas) —
    volta pro plano gratuito."""
    assinatura = (
        db.query(Assinatura)
        .filter(Assinatura.stripe_subscription_id == assinatura_stripe.get("id"))
        .first()
    )
    if assinatura is None:
        return
    _trocar_papel(assinatura.usuario_id, PLANO_GRATUITO)
    plano_encerrado = assinatura.plano
    assinatura.premium = False
    assinatura.plano = None
    db.commit()
    log_client.registrar_evento(assinatura.usuario_id, f"plano_cancelado:{plano_encerrado}")


_TRATADORES = {
    "checkout.session.completed": _ativar_plano,
    "customer.subscription.deleted": _encerrar_plano,
}


@router.post("/webhook", responses=RESP_ERROS_WEBHOOK | RESP_502_AUTH_SERVICE)
async def receber_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> dict:
    """Chamado PELO STRIPE, não pelo front — sem JWT: quem prova que a
    chamada é legítima é a assinatura no cabeçalho `Stripe-Signature`.

    Chega de forma assíncrona: pode vir antes ou depois do navegador
    voltar do checkout, e é a ÚNICA coisa que ativa um plano pago.

    `async` só pra ler o corpo bruto (`await request.body()`) — a
    assinatura é calculada sobre os bytes exatos que o Stripe mandou; se o
    FastAPI parseasse e re-serializasse o JSON, ela não bateria mais."""
    payload = await request.body()
    try:
        pagamentos.validar_webhook(payload, stripe_signature)
    except pagamentos.PagamentoNaoConfigurado as erro:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro)) from erro
    except pagamentos.AssinaturaWebhookInvalida as erro:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(erro)) from erro

    evento = json.loads(payload)
    tratador = _TRATADORES.get(evento.get("type"))
    # Evento que não interessa: 200 mesmo assim — erro faria o Stripe
    # ficar reenviando à toa.
    if tratador is not None:
        # Banco, auth-service e log-service são síncronos: roda fora do event loop.
        await run_in_threadpool(tratador, db, evento["data"]["object"])
    return {"recebido": True}
