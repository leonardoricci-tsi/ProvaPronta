import json
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import NIVEL_PAPEL, UsuarioAutenticado, get_current_user
from app.database import get_db
from app.models import Assinatura, EventoStripe
from app.openapi_responses import (
    RESP_401,
    RESP_409_PLANO,
    RESP_409_PORTAL,
    RESP_502_AUTH_SERVICE,
    RESP_ERROS_PAGAMENTO,
    RESP_ERROS_WEBHOOK,
)
from app.services import log_client, pagamentos
from app.services.auth_client import PapelNaoAtualizado, avisar_pagamento_recusado, definir_papel_pago

router = APIRouter(prefix="/premium", tags=["premium"])

# Plano gratuito: é pra ele que volta quem cancela um plano pago (ou deixa
# de pagar).
PLANO_GRATUITO = "professor"


class CheckoutIn(BaseModel):
    # Free (professor) não é vendido (é o gratuito); admin não é plano.
    plano: Literal["professor_pro", "coordenador"]


class CheckoutOut(BaseModel):
    checkout_url: str


class PortalOut(BaseModel):
    portal_url: str


class StatusPremiumOut(BaseModel):
    premium: bool
    # Plano pago ativo (professor_pro / coordenador), ou None no gratuito.
    plano: str | None
    # Status da assinatura no Stripe (active, past_due, canceled...), ou
    # None pra quem nunca assinou. `past_due` = pagamento recusado.
    status: str | None = None
    # Tem assinatura no Stripe pra gerenciar (portal do cliente).
    pode_gerenciar: bool = False


def plano_pago(db: Session, usuario_id: int) -> str | None:
    assinatura = db.get(Assinatura, usuario_id)
    return assinatura.plano if assinatura is not None and assinatura.premium else None


def _erro_pagamento(erro: Exception) -> HTTPException:
    if isinstance(erro, pagamentos.PagamentoNaoConfigurado):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(erro))
    return HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro))


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post(
    "/checkout",
    response_model=CheckoutOut,
    responses=RESP_401 | RESP_409_PLANO | RESP_ERROS_PAGAMENTO,
)
def criar_checkout(
    dados: CheckoutIn,
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CheckoutOut:
    """Abre o pagamento da assinatura mensal do plano escolhido no Stripe
    (Checkout Session com `mode=subscription`) e devolve a URL dela.

    Devolve a URL em vez de um 302 porque o front é uma SPA que se
    autentica por header (Bearer), não por cookie: um redirect do servidor
    não levaria o token. O front recebe a URL e faz o redirecionamento.

    A sessão é ligada ao customer do Stripe deste usuário, criado na
    primeira vez e guardado em `assinaturas`.

    Só deixa comprar um plano ACIMA do papel atual — comprar o mesmo ou um
    abaixo não daria nada a mais (admin já tem tudo)."""
    if NIVEL_PAPEL.get(usuario_atual.role, 0) >= NIVEL_PAPEL[dados.plano]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Você já tem esse plano ou um superior"
        )
    assinatura = db.get(Assinatura, usuario_atual.id)
    if assinatura is not None and assinatura.stripe_subscription_id and assinatura.status in ("past_due", "unpaid"):
        # A assinatura ainda existe no Stripe, só com a cobrança atrasada:
        # uma segunda assinatura cobraria duas vezes. Regulariza no portal.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sua assinatura está com o pagamento pendente. Atualize o cartão em Gerenciar assinatura",
        )
    try:
        if assinatura is None or not assinatura.stripe_customer_id:
            customer_id = pagamentos.criar_cliente(usuario_atual.id, usuario_atual.nome)
            if assinatura is None:
                assinatura = Assinatura(usuario_id=usuario_atual.id, premium=False)
                db.add(assinatura)
            assinatura.stripe_customer_id = customer_id
            db.commit()
        url = pagamentos.criar_checkout(usuario_atual.id, dados.plano, assinatura.stripe_customer_id)
    except (pagamentos.PagamentoNaoConfigurado, pagamentos.PagamentoIndisponivel) as erro:
        raise _erro_pagamento(erro) from erro
    log_client.registrar_evento(usuario_atual.id, f"abrir_checkout:{dados.plano}", ip=_ip(request))
    return CheckoutOut(checkout_url=url)


@router.post(
    "/portal",
    response_model=PortalOut,
    responses=RESP_401 | RESP_409_PORTAL | RESP_ERROS_PAGAMENTO,
)
def abrir_portal(
    request: Request,
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PortalOut:
    """"Gerenciar assinatura": abre o portal do cliente do Stripe (trocar
    de plano, cartão, cancelar). O que mudar lá chega pelos webhooks."""
    assinatura = db.get(Assinatura, usuario_atual.id)
    if assinatura is None or not assinatura.stripe_subscription_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Você ainda não tem uma assinatura para gerenciar"
        )
    try:
        url = pagamentos.criar_portal(assinatura.stripe_customer_id)
    except (pagamentos.PagamentoNaoConfigurado, pagamentos.PagamentoIndisponivel) as erro:
        raise _erro_pagamento(erro) from erro
    log_client.registrar_evento(usuario_atual.id, "abrir_portal_assinatura", ip=_ip(request))
    return PortalOut(portal_url=url)


@router.get("/status", response_model=StatusPremiumOut, responses=RESP_401)
def status_premium(
    usuario_atual: UsuarioAutenticado = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StatusPremiumOut:
    """O front consulta isso na volta do checkout: a confirmação do
    pagamento chega por outro caminho (webhook), e pode chegar depois do
    navegador voltar — então ele pergunta até o plano aparecer."""
    assinatura = db.get(Assinatura, usuario_atual.id)
    if assinatura is None:
        return StatusPremiumOut(premium=False, plano=None)
    return StatusPremiumOut(
        premium=assinatura.premium,
        plano=assinatura.plano if assinatura.premium else None,
        status=assinatura.status,
        pode_gerenciar=bool(assinatura.stripe_subscription_id and assinatura.status != "canceled"),
    )


# --- Webhook -----------------------------------------------------------------


def _trocar_papel(usuario_id: int, papel: str) -> None:
    try:
        definir_papel_pago(usuario_id, papel)
    except PapelNaoAtualizado as erro:
        # Erro de propósito: sem 2xx, o Stripe reenvia o evento mais tarde
        # (e processar de novo dá no mesmo) — o pagamento não se perde.
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(erro)) from erro


def _assinatura_do_evento(db: Session, subscription_id: str | None, customer_id: str | None) -> Assinatura | None:
    """A linha de quem é a assinatura do evento: pelo ID da assinatura; se
    ainda não foi gravado (evento chegou antes do checkout.session.completed),
    pelo customer — mas só numa linha SEM assinatura, senão um evento da
    assinatura antiga (cancelada numa troca de plano) mexeria na nova."""
    if subscription_id:
        assinatura = db.query(Assinatura).filter(Assinatura.stripe_subscription_id == subscription_id).first()
        if assinatura is not None:
            return assinatura
    if customer_id:
        return (
            db.query(Assinatura)
            .filter(Assinatura.stripe_customer_id == customer_id, Assinatura.stripe_subscription_id.is_(None))
            .first()
        )
    return None


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
    # Idempotente: processar duas vezes dá no mesmo resultado.
    assinatura.premium = True
    assinatura.plano = plano
    assinatura.status = "active"
    assinatura.stripe_customer_id = sessao.get("customer")
    assinatura.stripe_subscription_id = sessao.get("subscription")
    if sessao.get("amount_total") is not None:
        assinatura.valor_mensal_centavos = sessao["amount_total"]
    db.commit()

    # Trocou de plano pelo checkout (ex.: Pro -> Escola): cancela a
    # assinatura anterior. O cancelamento dispara outros webhooks, mas eles
    # não acham mais essa assinatura no banco (o ID já é o novo).
    if assinatura_antiga and assinatura_antiga != assinatura.stripe_subscription_id:
        pagamentos.cancelar_assinatura(assinatura_antiga)
    log_client.registrar_evento(usuario_id, f"plano_ativado:{plano}")


def _valor_mensal(assinatura_stripe: dict) -> tuple[str | None, int | None]:
    """(price_id, valor mensal em centavos) do primeiro item da assinatura."""
    itens = ((assinatura_stripe.get("items") or {}).get("data")) or []
    if not itens:
        return None, None
    preco = itens[0].get("price") or {}
    valor = preco.get("unit_amount")
    if valor is not None:
        valor *= itens[0].get("quantity") or 1
    return preco.get("id"), valor


def _atualizar_assinatura(db: Session, assinatura_stripe: dict) -> None:
    """customer.subscription.updated: mudou o plano (troca no portal), o
    status (pagamento recusado -> past_due, pago de novo -> active) ou o
    cancelamento foi agendado. O banco passa a refletir o que o Stripe diz."""
    assinatura = _assinatura_do_evento(db, assinatura_stripe.get("id"), assinatura_stripe.get("customer"))
    if assinatura is None:
        return
    if assinatura.status == "canceled" and assinatura.stripe_subscription_id == assinatura_stripe.get("id"):
        # Cancelada é estado final no Stripe. Os eventos não chegam em
        # ordem garantida: um `updated` (ainda "active") que chega DEPOIS do
        # `deleted` — ou um reenvio dele — não pode reativar o plano.
        return
    price_id, valor = _valor_mensal(assinatura_stripe)
    plano = pagamentos.plano_do_preco(price_id) or (assinatura_stripe.get("metadata") or {}).get("plano")
    status_stripe = assinatura_stripe.get("status")
    pagante = status_stripe in pagamentos.STATUS_PAGANTES and plano in pagamentos.PLANOS_PAGOS
    plano_antes = assinatura.plano if assinatura.premium else None

    if pagante and plano != plano_antes:
        _trocar_papel(assinatura.usuario_id, plano)
    elif not pagante and plano_antes:
        _trocar_papel(assinatura.usuario_id, PLANO_GRATUITO)

    assinatura.stripe_subscription_id = assinatura_stripe.get("id")
    assinatura.status = status_stripe
    assinatura.premium = pagante
    assinatura.plano = plano if pagante else None
    if valor is not None:
        assinatura.valor_mensal_centavos = valor
    db.commit()
    if pagante and plano != plano_antes:
        log_client.registrar_evento(assinatura.usuario_id, f"plano_alterado:{plano_antes or 'free'}:{plano}")
    elif not pagante and plano_antes:
        log_client.registrar_evento(assinatura.usuario_id, f"plano_suspenso:{plano_antes}:{status_stripe}")


def _encerrar_plano(db: Session, assinatura_stripe: dict) -> None:
    """customer.subscription.deleted: a assinatura acabou (cancelada no
    portal ou no painel do Stripe, ou cobrança recusada até esgotar as
    tentativas) — volta pro plano gratuito."""
    assinatura = (
        db.query(Assinatura)
        .filter(Assinatura.stripe_subscription_id == assinatura_stripe.get("id"))
        .first()
    )
    if assinatura is None:
        return
    plano_encerrado = assinatura.plano
    if assinatura.premium:
        _trocar_papel(assinatura.usuario_id, PLANO_GRATUITO)
    assinatura.premium = False
    assinatura.plano = None
    assinatura.status = "canceled"
    db.commit()
    log_client.registrar_evento(assinatura.usuario_id, f"plano_cancelado:{plano_encerrado or 'suspenso'}")


def _subscription_da_fatura(fatura: dict) -> str | None:
    # Versões novas da API do Stripe movem o ID pra `parent`.
    if isinstance(fatura.get("subscription"), str):
        return fatura["subscription"]
    detalhes = ((fatura.get("parent") or {}).get("subscription_details")) or {}
    return detalhes.get("subscription")


def _pagamento_recusado(db: Session, fatura: dict) -> None:
    """invoice.payment_failed: a cobrança do mês foi recusada. A conta fica
    inadimplente (`past_due`) e volta pro Free na hora — o Pro não continua
    de graça enquanto o Stripe tenta cobrar de novo. Se o pagamento passar
    depois, o customer.subscription.updated com `active` devolve o plano.
    A pessoa é avisada por e-mail e por um alerta no site."""
    assinatura = _assinatura_do_evento(db, _subscription_da_fatura(fatura), fatura.get("customer"))
    if assinatura is None:
        return
    plano = assinatura.plano
    if assinatura.premium:
        _trocar_papel(assinatura.usuario_id, PLANO_GRATUITO)
    assinatura.premium = False
    assinatura.plano = None
    assinatura.status = "past_due"
    db.commit()
    avisar_pagamento_recusado(assinatura.usuario_id, plano)
    log_client.registrar_evento(assinatura.usuario_id, f"pagamento_recusado:{plano or 'sem_plano'}")


_TRATADORES = {
    "checkout.session.completed": _ativar_plano,
    "customer.subscription.updated": _atualizar_assinatura,
    "customer.subscription.deleted": _encerrar_plano,
    "invoice.payment_failed": _pagamento_recusado,
}


def _ja_processado(db: Session, evento_id: str | None) -> bool:
    return bool(evento_id) and db.get(EventoStripe, evento_id) is not None


def _marcar_processado(db: Session, evento_id: str | None, tipo: str) -> None:
    if not evento_id:
        return
    db.add(EventoStripe(id=evento_id, tipo=tipo))
    try:
        db.commit()
    except IntegrityError:
        # Duas entregas do mesmo evento ao mesmo tempo: a outra já marcou.
        db.rollback()


@router.post("/webhook", responses=RESP_ERROS_WEBHOOK | RESP_502_AUTH_SERVICE)
async def receber_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
) -> dict:
    """Chamado PELO STRIPE, não pelo front — sem JWT: quem prova que a
    chamada é legítima é a assinatura no cabeçalho `Stripe-Signature`.

    Chega de forma assíncrona: pode vir antes ou depois do navegador
    voltar do checkout, e é a ÚNICA coisa que muda o plano de alguém.

    O mesmo evento entregue de novo (mesmo `id`) é ignorado: responde 200
    sem processar outra vez.

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
    tipo = evento.get("type", "")
    tratador = _TRATADORES.get(tipo)
    # Evento que não interessa: 200 mesmo assim — erro faria o Stripe
    # ficar reenviando à toa.
    if tratador is None:
        return {"recebido": True}
    if await run_in_threadpool(_ja_processado, db, evento.get("id")):
        return {"recebido": True, "repetido": True}
    # Banco, auth-service e log-service são síncronos: roda fora do event loop.
    await run_in_threadpool(tratador, db, evento["data"]["object"])
    await run_in_threadpool(_marcar_processado, db, evento.get("id"), tipo)
    return {"recebido": True}
