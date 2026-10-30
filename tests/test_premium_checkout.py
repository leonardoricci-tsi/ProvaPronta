from types import SimpleNamespace

import pytest
import stripe

from app.config import get_settings
from app.models import Assinatura
from app.services import pagamentos
from tests.conftest import auth_headers, criar_token


class StripeFalso:
    """Faz o papel do StripeClient: guarda o que o catálogo pediu e devolve
    uma sessão com URL — nenhuma chamada sai pra rede."""

    def __init__(self, erro: Exception | None = None):
        self.params = None
        self.erro = erro
        self.v1 = SimpleNamespace(checkout=SimpleNamespace(sessions=self))

    def create(self, params):
        if self.erro:
            raise self.erro
        self.params = params
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_test_123")


@pytest.fixture()
def stripe_configurado(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_fake")
    monkeypatch.setattr(settings, "stripe_price_escola", "price_escola_fake")
    falso = StripeFalso()
    monkeypatch.setattr(pagamentos, "_client", falso)
    return falso


def checkout(client, token, plano):
    return client.post("/premium/checkout", json={"plano": plano}, headers=auth_headers(token))


def test_professor_compra_pro_com_o_preco_e_o_usuario_certos(client, auth_service, stripe_configurado):
    resposta = checkout(client, criar_token(usuario_id=77, role="professor"), "professor_pro")

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"checkout_url": "https://checkout.stripe.com/c/pay/cs_test_123"}
    params = stripe_configurado.params
    assert params["mode"] == "subscription"
    assert params["line_items"] == [{"price": "price_pro_fake", "quantity": 1}]
    # É isso que o webhook usa pra saber quem pagou e qual plano.
    assert params["client_reference_id"] == "77"
    assert params["metadata"] == {"usuario_id": "77", "plano": "professor_pro"}
    assert params["subscription_data"]["metadata"] == {"usuario_id": "77", "plano": "professor_pro"}


def test_pro_pode_subir_pra_escola(client, auth_service, stripe_configurado):
    resposta = checkout(client, criar_token(role="professor_pro"), "coordenador")

    assert resposta.status_code == 200
    assert stripe_configurado.params["line_items"][0]["price"] == "price_escola_fake"


@pytest.mark.parametrize(
    ("papel", "plano"),
    [
        ("professor_pro", "professor_pro"),
        ("coordenador", "professor_pro"),
        ("coordenador", "coordenador"),
        ("admin", "coordenador"),
    ],
)
def test_nao_vende_plano_igual_ou_abaixo_do_papel_atual(client, stripe_configurado, papel, plano):
    resposta = checkout(client, criar_token(role=papel), plano)

    assert resposta.status_code == 409
    assert stripe_configurado.params is None


def test_professor_nao_e_vendido_e_plano_inexistente_e_recusado(client, stripe_configurado):
    token = criar_token(role="professor")

    assert checkout(client, token, "professor").status_code == 422
    assert checkout(client, token, "admin").status_code == 422


def test_checkout_exige_login(client):
    assert client.post("/premium/checkout", json={"plano": "professor_pro"}).status_code == 401


def test_sem_chaves_do_stripe_checkout_responde_503(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "stripe_secret_key", "")

    assert checkout(client, criar_token(role="professor"), "professor_pro").status_code == 503


def test_stripe_fora_do_ar_vira_502(client, stripe_configurado):
    stripe_configurado.erro = stripe.APIConnectionError("sem rede")

    assert checkout(client, criar_token(role="professor"), "professor_pro").status_code == 502


def test_status_do_plano(client, db_session):
    db_session.add(Assinatura(usuario_id=79, premium=True, plano="professor_pro"))
    db_session.commit()

    assert client.get("/premium/status", headers=auth_headers(criar_token(usuario_id=79))).json() == {
        "premium": True,
        "plano": "professor_pro",
    }
    # Sem linha em `assinaturas` = plano gratuito.
    assert client.get("/premium/status", headers=auth_headers(criar_token(usuario_id=80))).json() == {
        "premium": False,
        "plano": None,
    }


def test_perfil_mostra_o_plano_pago(client, db_session, auth_service):
    db_session.add(Assinatura(usuario_id=64, premium=True, plano="coordenador"))
    db_session.commit()
    quem_ve = auth_headers(criar_token(usuario_id=65))

    assert client.get("/profiles/64", headers=quem_ve).json()["plano"] == "coordenador"
    assert client.get("/profiles/65", headers=quem_ve).json()["plano"] is None
