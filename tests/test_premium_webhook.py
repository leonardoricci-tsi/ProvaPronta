import hashlib
import hmac
import json
import time

import jwt
import pytest
from httpx import Response

from app.config import get_settings
from app.models import Assinatura
from app.services import pagamentos

SEGREDO = "whsec_teste_fake"


@pytest.fixture(autouse=True)
def webhook_configurado(monkeypatch):
    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", SEGREDO)


@pytest.fixture()
def cancelamentos(monkeypatch):
    """Assinaturas que o catálogo mandou cancelar no Stripe (troca de plano)."""
    cancelados = []
    monkeypatch.setattr(pagamentos, "cancelar_assinatura", cancelados.append)
    return cancelados


def assinar(corpo: bytes, segredo: str = SEGREDO, timestamp: int | None = None) -> str:
    """Monta o cabeçalho Stripe-Signature do jeito que o Stripe monta:
    HMAC-SHA256 de "<timestamp>.<corpo>" com o segredo do endpoint."""
    timestamp = timestamp or int(time.time())
    mac = hmac.new(segredo.encode(), f"{timestamp}.".encode() + corpo, hashlib.sha256)
    return f"t={timestamp},v1={mac.hexdigest()}"


def evento_checkout(usuario_id: int = 42, plano: str = "professor_pro", subscription: str = "sub_test_1") -> bytes:
    return json.dumps(
        {
            "id": "evt_test_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "object": "checkout.session",
                    "mode": "subscription",
                    "client_reference_id": str(usuario_id),
                    "metadata": {"usuario_id": str(usuario_id), "plano": plano},
                    "customer": "cus_test_1",
                    "subscription": subscription,
                    "payment_status": "paid",
                }
            },
        }
    ).encode()


def evento_cancelamento(subscription: str) -> bytes:
    return json.dumps(
        {
            "type": "customer.subscription.deleted",
            "data": {"object": {"object": "subscription", "id": subscription}},
        }
    ).encode()


def enviar(client, corpo: bytes, assinatura: str | None):
    headers = {"Content-Type": "application/json"}
    if assinatura is not None:
        headers["Stripe-Signature"] = assinatura
    return client.post("/premium/webhook", content=corpo, headers=headers)


def papeis_definidos(auth_service) -> list[tuple[str, str]]:
    """(url, papel) de cada troca de papel pedida ao auth-service."""
    return [
        (str(chamada.request.url), json.loads(chamada.request.content)["role"])
        for chamada in auth_service.routes["definir_papel"].calls
    ]


def test_pagamento_confirmado_ativa_o_plano_e_troca_o_papel(client, db_session, auth_service):
    corpo = evento_checkout(usuario_id=42, plano="professor_pro")

    resposta = enviar(client, corpo, assinar(corpo))

    assert resposta.status_code == 200, resposta.text
    assinatura = db_session.get(Assinatura, 42)
    assert (assinatura.premium, assinatura.plano) == (True, "professor_pro")
    assert assinatura.stripe_customer_id == "cus_test_1"
    assert assinatura.stripe_subscription_id == "sub_test_1"
    assert papeis_definidos(auth_service) == [
        ("http://127.0.0.1:9/internal/users/42/role", "professor_pro")
    ]


def test_troca_de_papel_usa_token_de_servico_nao_de_usuario(client, auth_service):
    corpo = evento_checkout(usuario_id=43)
    enviar(client, corpo, assinar(corpo))

    cabecalho = auth_service.routes["definir_papel"].calls.last.request.headers["Authorization"]
    payload = jwt.decode(
        cabecalho.removeprefix("Bearer "), get_settings().jwt_secret, algorithms=["HS256"]
    )
    assert payload["servico"] == "catalogo"
    # Sem `sub`: não serve como token de usuário em lugar nenhum.
    assert "sub" not in payload


def test_mesmo_evento_duas_vezes_nao_quebra(client, db_session, auth_service, cancelamentos):
    corpo = evento_checkout(usuario_id=44)

    assert enviar(client, corpo, assinar(corpo)).status_code == 200
    assert enviar(client, corpo, assinar(corpo)).status_code == 200

    assert db_session.query(Assinatura).filter_by(usuario_id=44).count() == 1
    assert cancelamentos == []


def test_subir_de_pro_pra_escola_cancela_a_assinatura_antiga(
    client, db_session, auth_service, cancelamentos
):
    db_session.add(Assinatura(usuario_id=45, premium=True, plano="professor_pro", stripe_subscription_id="sub_pro"))
    db_session.commit()
    corpo = evento_checkout(usuario_id=45, plano="coordenador", subscription="sub_escola")

    assert enviar(client, corpo, assinar(corpo)).status_code == 200

    assinatura = db_session.get(Assinatura, 45)
    assert (assinatura.plano, assinatura.stripe_subscription_id) == ("coordenador", "sub_escola")
    assert cancelamentos == ["sub_pro"]


def test_auth_service_fora_do_ar_responde_502_e_nao_grava(client, db_session, auth_service):
    """Sem 2xx o Stripe reenvia o evento depois — o pagamento não se perde."""
    auth_service.routes["definir_papel"].mock(return_value=Response(500))
    corpo = evento_checkout(usuario_id=46)

    assert enviar(client, corpo, assinar(corpo)).status_code == 502
    assert db_session.get(Assinatura, 46) is None


def test_plano_desconhecido_no_metadata_e_ignorado(client, db_session, auth_service):
    corpo = evento_checkout(usuario_id=47, plano="admin")

    assert enviar(client, corpo, assinar(corpo)).status_code == 200
    assert db_session.get(Assinatura, 47) is None
    assert papeis_definidos(auth_service) == []


def test_sem_cabecalho_de_assinatura_e_recusado(client, db_session):
    resposta = enviar(client, evento_checkout(usuario_id=50), None)

    assert resposta.status_code == 400
    assert db_session.get(Assinatura, 50) is None


def test_assinado_com_outro_segredo_e_recusado(client, db_session):
    corpo = evento_checkout(usuario_id=51)

    resposta = enviar(client, corpo, assinar(corpo, segredo="whsec_de_um_atacante"))

    assert resposta.status_code == 400
    assert db_session.get(Assinatura, 51) is None


def test_corpo_alterado_depois_de_assinado_e_recusado(client, db_session):
    """Assinatura de um evento legítimo do usuário 52, corpo trocado pro 53."""
    assinatura = assinar(evento_checkout(usuario_id=52))

    resposta = enviar(client, evento_checkout(usuario_id=53), assinatura)

    assert resposta.status_code == 400
    assert db_session.get(Assinatura, 53) is None


def test_evento_velho_reenviado_e_recusado(client, db_session):
    corpo = evento_checkout(usuario_id=54)
    uma_hora_atras = int(time.time()) - 3600

    resposta = enviar(client, corpo, assinar(corpo, timestamp=uma_hora_atras))

    assert resposta.status_code == 400
    assert db_session.get(Assinatura, 54) is None


def test_sem_segredo_configurado_responde_503(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "")
    corpo = evento_checkout()

    assert enviar(client, corpo, assinar(corpo)).status_code == 503


def test_assinatura_cancelada_volta_pro_plano_gratuito(client, db_session, auth_service):
    db_session.add(Assinatura(usuario_id=55, premium=True, plano="professor_pro", stripe_subscription_id="sub_55"))
    db_session.commit()
    corpo = evento_cancelamento("sub_55")

    assert enviar(client, corpo, assinar(corpo)).status_code == 200

    assinatura = db_session.get(Assinatura, 55)
    db_session.refresh(assinatura)
    assert (assinatura.premium, assinatura.plano) == (False, None)
    assert papeis_definidos(auth_service)[-1][1] == "professor"


def test_cancelamento_de_assinatura_ja_trocada_nao_rebaixa_ninguem(client, db_session, auth_service):
    """O cancelamento da assinatura antiga (troca de plano) também vira
    webhook — mas o banco já guarda a nova, então nada muda."""
    db_session.add(
        Assinatura(usuario_id=56, premium=True, plano="coordenador", stripe_subscription_id="sub_novo")
    )
    db_session.commit()
    corpo = evento_cancelamento("sub_antigo")

    assert enviar(client, corpo, assinar(corpo)).status_code == 200
    assert db_session.get(Assinatura, 56).plano == "coordenador"
    assert papeis_definidos(auth_service) == []


def test_evento_que_nao_interessa_responde_200_sem_mexer_no_banco(client, db_session):
    corpo = json.dumps({"type": "invoice.paid", "data": {"object": {}}}).encode()

    assert enviar(client, corpo, assinar(corpo)).status_code == 200
    assert db_session.query(Assinatura).count() == 0
