"""Atividade 11 (SaaS completo): a assinatura mensal acompanhada pelos
webhooks — troca de plano e cancelamento no portal, pagamento recusado,
evento repetido — e o resumo do admin com o MRR de teste."""

import json

import pytest
from httpx import Response

from app.config import get_settings
from app.models import Assinatura, EventoStripe
from tests.conftest import auth_headers, criar_token
from tests.test_premium_webhook import SEGREDO, assinar, enviar, evento_checkout, papeis_definidos

PRECO_PRO, PRECO_ESCOLA = "price_pro_fake", "price_escola_fake"


@pytest.fixture(autouse=True)
def precos(monkeypatch):
    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", SEGREDO)
    monkeypatch.setattr(get_settings(), "stripe_price_pro", PRECO_PRO)
    monkeypatch.setattr(get_settings(), "stripe_price_escola", PRECO_ESCOLA)


@pytest.fixture()
def avisos(auth_service):
    """O pedido de e-mail de "pagamento recusado" pro auth-service."""
    url = get_settings().auth_service_url
    return auth_service.post(url__regex=rf"{url}/internal/users/\d+/aviso-pagamento-recusado").mock(
        return_value=Response(202, json={"aviso": "enviando"})
    )


def evento(tipo: str, objeto: dict, evento_id: str | None = None) -> bytes:
    return json.dumps({"id": evento_id or f"evt_{tipo}_{id(objeto)}", "type": tipo, "data": {"object": objeto}}).encode()


def assinatura_stripe(sub="sub_1", customer="cus_1", status="active", preco=PRECO_PRO, valor=2990) -> dict:
    return {
        "object": "subscription",
        "id": sub,
        "customer": customer,
        "status": status,
        "metadata": {"plano": "professor_pro"},  # o do checkout; fica velho após troca no portal
        "items": {"data": [{"price": {"id": preco, "unit_amount": valor}, "quantity": 1}]},
    }


def mandar(client, corpo: bytes):
    resposta = enviar(client, corpo, assinar(corpo))
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def pro_ativo(db_session, usuario_id=50, sub="sub_1", customer="cus_1"):
    db_session.add(
        Assinatura(
            usuario_id=usuario_id, premium=True, plano="professor_pro", status="active",
            stripe_customer_id=customer, stripe_subscription_id=sub, valor_mensal_centavos=2990,
        )
    )
    db_session.commit()


def test_checkout_concluido_guarda_status_e_valor_mensal(client, db_session, auth_service):
    corpo = json.loads(evento_checkout(usuario_id=51))
    corpo["data"]["object"]["amount_total"] = 2990
    mandar(client, json.dumps(corpo).encode())

    assinatura = db_session.get(Assinatura, 51)
    assert (assinatura.status, assinatura.valor_mensal_centavos, assinatura.premium) == ("active", 2990, True)


def test_troca_de_plano_no_portal_vale_pelo_preco_nao_pelo_metadata(client, db_session, auth_service):
    pro_ativo(db_session)

    mandar(client, evento("customer.subscription.updated", assinatura_stripe(preco=PRECO_ESCOLA, valor=19990)))

    assinatura = db_session.get(Assinatura, 50)
    assert (assinatura.plano, assinatura.valor_mensal_centavos, assinatura.premium) == ("coordenador", 19990, True)
    assert papeis_definidos(auth_service)[-1][1] == "coordenador"


def test_update_sem_mudanca_nao_troca_papel(client, db_session, auth_service):
    """Ex.: cancelamento agendado pro fim do mês — status continua active."""
    pro_ativo(db_session)

    mandar(client, evento("customer.subscription.updated", assinatura_stripe()))

    assert papeis_definidos(auth_service) == []
    assert db_session.get(Assinatura, 50).premium is True


def test_pagamento_recusado_volta_pro_free_avisa_e_o_pagamento_depois_devolve_o_plano(
    client, db_session, auth_service, avisos
):
    pro_ativo(db_session)
    fatura = {"object": "invoice", "customer": "cus_1", "subscription": "sub_1"}

    mandar(client, evento("invoice.payment_failed", fatura))

    assinatura = db_session.get(Assinatura, 50)
    assert (assinatura.premium, assinatura.plano, assinatura.status) == (False, None, "past_due")
    assert papeis_definidos(auth_service)[-1][1] == "professor"
    assert avisos.call_count == 1
    assert json.loads(avisos.calls.last.request.content) == {"plano": "professor_pro"}
    status_site = client.get("/premium/status", headers=auth_headers(criar_token(usuario_id=50))).json()
    assert (status_site["premium"], status_site["status"]) == (False, "past_due")

    # O Stripe tenta de novo, o cartão passa: a assinatura volta a active.
    mandar(client, evento("customer.subscription.updated", assinatura_stripe(status="active")))

    assinatura = db_session.get(Assinatura, 50)
    assert (assinatura.premium, assinatura.plano, assinatura.status) == (True, "professor_pro", "active")
    assert papeis_definidos(auth_service)[-1][1] == "professor_pro"


def test_fatura_no_formato_novo_da_api_tambem_e_entendida(client, db_session, auth_service, avisos):
    pro_ativo(db_session)
    fatura = {
        "object": "invoice",
        "customer": "cus_1",
        "parent": {"subscription_details": {"subscription": "sub_1"}},
    }

    mandar(client, evento("invoice.payment_failed", fatura))

    assert db_session.get(Assinatura, 50).status == "past_due"


def test_past_due_pelo_update_tambem_suspende(client, db_session, auth_service):
    pro_ativo(db_session)

    mandar(client, evento("customer.subscription.updated", assinatura_stripe(status="past_due")))

    assert db_session.get(Assinatura, 50).premium is False
    assert papeis_definidos(auth_service)[-1][1] == "professor"


def test_cancelar_no_portal_volta_pro_free(client, db_session, auth_service):
    pro_ativo(db_session)

    mandar(client, evento("customer.subscription.deleted", assinatura_stripe(status="canceled")))

    assinatura = db_session.get(Assinatura, 50)
    assert (assinatura.premium, assinatura.plano, assinatura.status) == (False, None, "canceled")
    assert papeis_definidos(auth_service)[-1][1] == "professor"


def test_mesmo_evento_duas_vezes_so_tem_efeito_uma_vez(client, db_session, auth_service, avisos):
    pro_ativo(db_session)
    corpo = evento("invoice.payment_failed", {"customer": "cus_1", "subscription": "sub_1"}, evento_id="evt_repetido")

    assert mandar(client, corpo) == {"recebido": True}
    assert mandar(client, corpo) == {"recebido": True, "repetido": True}

    # Um e-mail só, uma troca de papel só.
    assert avisos.call_count == 1
    assert len(papeis_definidos(auth_service)) == 1
    assert db_session.get(EventoStripe, "evt_repetido").tipo == "invoice.payment_failed"


def test_evento_que_falhou_nao_e_marcado_e_o_reenvio_processa(client, db_session, auth_service):
    pro_ativo(db_session)
    rota = auth_service.routes["definir_papel"]
    rota.mock(return_value=Response(503))
    corpo = evento("customer.subscription.deleted", assinatura_stripe(), evento_id="evt_falhou")

    assert enviar(client, corpo, assinar(corpo)).status_code == 502
    assert db_session.get(EventoStripe, "evt_falhou") is None

    rota.mock(side_effect=lambda request, id: Response(200, json={"id": int(id)}))
    assert mandar(client, corpo) == {"recebido": True}
    assert db_session.get(Assinatura, 50).premium is False


def test_update_atrasado_depois_do_cancelamento_nao_reativa(client, db_session, auth_service):
    """O portal manda `deleted` e `updated` quase juntos e a ordem não é
    garantida: um `updated` ainda "active" chegando depois não reativa."""
    pro_ativo(db_session)
    mandar(client, evento("customer.subscription.deleted", assinatura_stripe(status="canceled")))

    mandar(client, evento("customer.subscription.updated", assinatura_stripe(status="active")))

    assinatura = db_session.get(Assinatura, 50)
    assert (assinatura.premium, assinatura.status) == (False, "canceled")
    assert [papel for _, papel in papeis_definidos(auth_service)] == ["professor"]


def test_update_da_assinatura_antiga_depois_de_trocar_de_plano_nao_mexe_na_nova(client, db_session, auth_service):
    """Pro -> Escola pelo checkout: a assinatura antiga é cancelada e o
    Stripe manda o update dela; a linha já aponta pra nova e não muda."""
    pro_ativo(db_session, sub="sub_escola")
    db_session.get(Assinatura, 50).plano = "coordenador"
    db_session.commit()

    mandar(client, evento("customer.subscription.updated", assinatura_stripe(sub="sub_pro_velha", status="canceled")))

    assinatura = db_session.get(Assinatura, 50)
    assert (assinatura.premium, assinatura.plano, assinatura.stripe_subscription_id) == (True, "coordenador", "sub_escola")
    assert papeis_definidos(auth_service) == []


def test_update_que_chega_antes_do_checkout_acha_o_usuario_pelo_customer(client, db_session, auth_service):
    # O checkout já criou o customer (e só ele) pra este usuário.
    db_session.add(Assinatura(usuario_id=52, premium=False, stripe_customer_id="cus_52"))
    db_session.commit()

    mandar(client, evento("customer.subscription.updated", assinatura_stripe(sub="sub_52", customer="cus_52")))

    assinatura = db_session.get(Assinatura, 52)
    assert (assinatura.premium, assinatura.plano, assinatura.stripe_subscription_id) == (True, "professor_pro", "sub_52")


# --- Painel do admin ---------------------------------------------------------


@pytest.fixture()
def usuarios_e_logs(auth_service):
    settings = get_settings()
    usuarios = [
        {"id": 1, "role": "professor"}, {"id": 2, "role": "professor"}, {"id": 3, "role": "professor_pro"},
        {"id": 4, "role": "coordenador"}, {"id": 5, "role": "admin"},
    ]
    auth_service.get(f"{settings.auth_service_url}/auth/admin/users").mock(return_value=Response(200, json=usuarios))
    auth_service.get(f"{settings.log_service_url}/logs").mock(
        return_value=Response(200, json=[{"usuario_id": 3, "acao": "plano_ativado:professor_pro"}])
    )


def test_resumo_do_admin_com_usuarios_por_plano_e_mrr(client, db_session, usuarios_e_logs):
    db_session.add_all(
        [
            Assinatura(usuario_id=3, premium=True, plano="professor_pro", status="active", valor_mensal_centavos=2990),
            Assinatura(usuario_id=4, premium=True, plano="coordenador", status="active", valor_mensal_centavos=19990),
            Assinatura(usuario_id=6, premium=False, status="past_due", valor_mensal_centavos=2990),
            Assinatura(usuario_id=7, premium=False, status="canceled", valor_mensal_centavos=2990),
        ]
    )
    db_session.commit()

    resposta = client.get("/admin/resumo", headers=auth_headers(criar_token(role="admin")))

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["usuarios_por_plano"] == {"professor": 2, "professor_pro": 1, "coordenador": 1, "admin": 1}
    assert corpo["total_usuarios"] == 5
    assert corpo["assinaturas_ativas"] == 2
    assert corpo["assinaturas_ativas_por_plano"] == {"professor_pro": 1, "coordenador": 1}
    assert corpo["inadimplentes"] == 1
    # Só as ativas entram no MRR: R$ 29,90 + R$ 199,90.
    assert corpo["mrr_centavos"] == 22980
    assert corpo["eventos_recentes"][0]["acao"] == "plano_ativado:professor_pro"


def test_mrr_usa_o_preco_do_plano_para_assinatura_antiga_sem_valor(client, db_session, usuarios_e_logs, monkeypatch):
    from app.services import pagamentos

    monkeypatch.setattr(pagamentos, "_valores_dos_planos", {"professor_pro": 2990})
    db_session.add(Assinatura(usuario_id=8, premium=True, plano="professor_pro", status="active"))
    db_session.commit()

    corpo = client.get("/admin/resumo", headers=auth_headers(criar_token(role="admin"))).json()

    assert corpo["mrr_centavos"] == 2990


@pytest.mark.parametrize("papel", ["professor", "professor_pro", "coordenador"])
def test_resumo_so_para_admin(client, papel):
    assert client.get("/admin/resumo", headers=auth_headers(criar_token(role=papel))).status_code == 403
