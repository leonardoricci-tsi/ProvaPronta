import stripe

from app.config import get_settings

_client: stripe.StripeClient | None = None

# Planos à venda (atividade 7) — cada um é o papel que o usuário recebe.
# Free (professor) não está aqui: é o plano gratuito, papel padrão do cadastro.
PLANOS_PAGOS = ("professor_pro", "coordenador")


class PagamentoNaoConfigurado(Exception):
    """Chaves/preços do Stripe vazios — venda de planos desligada neste ambiente."""


class PagamentoIndisponivel(Exception):
    """O Stripe não respondeu ou recusou a chamada."""


class AssinaturaWebhookInvalida(Exception):
    """A requisição no /premium/webhook não foi assinada pelo Stripe."""


def _preco_do_plano(plano: str) -> str:
    settings = get_settings()
    return {"professor_pro": settings.stripe_price_pro, "coordenador": settings.stripe_price_escola}[
        plano
    ]


def _get_client() -> stripe.StripeClient:
    global _client
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise PagamentoNaoConfigurado("Venda de planos indisponível neste ambiente")
    # Chave de teste (sk_test_...) sempre: a atividade inteira roda no modo
    # de teste do Stripe, nenhuma cobrança real.
    if _client is None:
        _client = stripe.StripeClient(settings.stripe_secret_key)
    return _client


def criar_checkout(usuario_id: int, plano: str) -> str:
    """Cria a Checkout Session da assinatura do plano e devolve a URL da
    página de pagamento — hospedada pelo Stripe, é lá (e não aqui) que o
    cartão é digitado.

    `client_reference_id` é o que liga o pagamento ao usuário: o Stripe
    devolve esse valor intacto no webhook. Vem do JWT de quem chamou,
    nunca do corpo da requisição. O plano vai no `metadata`, também
    devolvido no webhook."""
    settings = get_settings()
    preco = _preco_do_plano(plano)
    client = _get_client()
    if not preco:
        raise PagamentoNaoConfigurado("Venda de planos indisponível neste ambiente")
    metadata = {"usuario_id": str(usuario_id), "plano": plano}
    try:
        sessao = client.v1.checkout.sessions.create(
            params={
                "mode": "subscription",
                "line_items": [{"price": preco, "quantity": 1}],
                "client_reference_id": str(usuario_id),
                "metadata": metadata,
                # Também na assinatura: o evento de cancelamento
                # (customer.subscription.deleted) não traz a sessão, só ela.
                "subscription_data": {"metadata": metadata},
                "success_url": f"{settings.catalog_public_url}/app/planos?checkout=sucesso",
                "cancel_url": f"{settings.catalog_public_url}/app/planos?checkout=cancelado",
            }
        )
    except stripe.StripeError as erro:
        raise PagamentoIndisponivel("Provedor de pagamento indisponível no momento") from erro
    return sessao.url


def cancelar_assinatura(subscription_id: str) -> None:
    """Troca de plano (Pro -> Escola): a assinatura antiga é cancelada pra
    ninguém pagar dois planos ao mesmo tempo. Melhor esforço — se falhar, o
    plano novo já está ativo e a antiga pode ser cancelada no painel."""
    try:
        _get_client().v1.subscriptions.cancel(subscription_id)
    except (stripe.StripeError, PagamentoNaoConfigurado):
        pass


def validar_webhook(payload: bytes, assinatura: str | None) -> None:
    """Confere o cabeçalho `Stripe-Signature`: um HMAC-SHA256 do corpo
    BRUTO com o segredo do endpoint (whsec_...), que só o Stripe e este
    servidor conhecem, mais um timestamp (rejeita reenvio de evento velho,
    tolerância de 5 min). A rota é pública — sem isso, qualquer um com
    um `curl` se daria um plano pago de graça."""
    segredo = get_settings().stripe_webhook_secret
    if not segredo:
        raise PagamentoNaoConfigurado("Webhook do Stripe não configurado neste ambiente")
    try:
        stripe.WebhookSignature.verify_header(
            payload, assinatura, segredo, tolerance=stripe.Webhook.DEFAULT_TOLERANCE
        )
    except stripe.SignatureVerificationError as erro:
        raise AssinaturaWebhookInvalida("Assinatura do webhook inválida") from erro
