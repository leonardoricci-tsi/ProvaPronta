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
        self.clientes: list[dict] = []
        self.portais: list[dict] = []
        self.v1 = SimpleNamespace(
            checkout=SimpleNamespace(sessions=self),
            customers=SimpleNamespace(create=self._criar_cliente),
            billing_portal=SimpleNamespace(sessions=SimpleNamespace(create=self._criar_portal)),
        )

    def create(self, params):
        if self.erro:
            raise self.erro
        self.params = params
        return SimpleNamespace(url="https://checkout.stripe.com/c/pay/cs_test_123")

    def _criar_cliente(self, params):
        if self.erro:
            raise self.erro
        self.clientes.append(params)
        return SimpleNamespace(id=f"cus_fake_{len(self.clientes)}")

    def _criar_portal(self, params):
        if self.erro:
            raise self.erro
        self.portais.append(params)
        return SimpleNamespace(url="https://billing.stripe.com/p/session/test_123")


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
    # Atividade 11: a sessão é ligada a um customer do Stripe guardado no usuário.
    assert stripe_configurado.clientes == [{"name": "Usuário Teste", "metadata": {"usuario_id": "77"}}]
    assert params["customer"] == "cus_fake_1"


def test_customer_e_criado_uma_vez_so_e_fica_guardado(client, db_session, auth_service, stripe_configurado):
    token = criar_token(usuario_id=78, role="professor")

    checkout(client, token, "professor_pro")
    checkout(client, token, "professor_pro")

    assert len(stripe_configurado.clientes) == 1
    assinatura = db_session.get(Assinatura, 78)
    # Guardado, mas ainda sem plano: só o webhook ativa.
    assert (assinatura.stripe_customer_id, assinatura.premium) == ("cus_fake_1", False)
    assert stripe_configurado.params["customer"] == "cus_fake_1"


def test_portal_do_cliente_abre_pra_quem_tem_assinatura(client, db_session, auth_service, stripe_configurado):
    db_session.add(
        Assinatura(
            usuario_id=81, premium=True, plano="professor_pro", status="active",
            stripe_customer_id="cus_81", stripe_subscription_id="sub_81",
        )
    )
    db_session.commit()

    resposta = client.post("/premium/portal", headers=auth_headers(criar_token(usuario_id=81)))

    assert resposta.status_code == 200, resposta.text
    assert resposta.json() == {"portal_url": "https://billing.stripe.com/p/session/test_123"}
    assert stripe_configurado.portais[0]["customer"] == "cus_81"
    assert stripe_configurado.portais[0]["return_url"].endswith("/app/planos?portal=voltou")
    status_atual = client.get("/premium/status", headers=auth_headers(criar_token(usuario_id=81))).json()
    assert status_atual["pode_gerenciar"] is True


def test_inadimplente_nao_assina_de_novo_regulariza_no_portal(client, db_session, auth_service, stripe_configurado):
    db_session.add(
        Assinatura(usuario_id=83, premium=False, status="past_due", stripe_customer_id="cus_83", stripe_subscription_id="sub_83")
    )
    db_session.commit()

    resposta = checkout(client, criar_token(usuario_id=83, role="professor"), "professor_pro")

    assert resposta.status_code == 409
    assert "Gerenciar assinatura" in resposta.json()["detail"]
    assert stripe_configurado.params is None


def test_portal_sem_assinatura_da_409(client, stripe_configurado):
    resposta = client.post("/premium/portal", headers=auth_headers(criar_token(usuario_id=82)))
    assert resposta.status_code == 409


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
        "status": None,
        "pode_gerenciar": False,
    }
    # Sem linha em `assinaturas` = plano gratuito.
    assert client.get("/premium/status", headers=auth_headers(criar_token(usuario_id=80))).json() == {
        "premium": False,
        "plano": None,
        "status": None,
        "pode_gerenciar": False,
    }


def test_perfil_mostra_o_plano_pago(client, db_session, auth_service):
    db_session.add(Assinatura(usuario_id=64, premium=True, plano="coordenador"))
    db_session.commit()
    quem_ve = auth_headers(criar_token(usuario_id=65))

    assert client.get("/profiles/64", headers=quem_ve).json()["plano"] == "coordenador"
    assert client.get("/profiles/65", headers=quem_ve).json()["plano"] is None
