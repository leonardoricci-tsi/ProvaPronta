import respx
from httpx import Response

from app.config import get_settings
from tests.conftest import auth_headers, criar_token

LOG_SERVICE_URL = get_settings().log_service_url


@respx.mock
def test_tentativa_negada_em_rota_admin_registra_evento(client):
    rota_mock = respx.post(f"{LOG_SERVICE_URL}/logs").mock(return_value=Response(201, json={"id": "1-0"}))
    token_comum = criar_token(role="nerd")

    resposta = client.get("/admin/logs", headers=auth_headers(token_comum))

    assert resposta.status_code == 403
    assert rota_mock.called
    assert b"acesso_negado:admin" in rota_mock.calls.last.request.content


@respx.mock
def test_logout_registra_evento(client):
    rota_mock = respx.post(f"{LOG_SERVICE_URL}/logs").mock(return_value=Response(201, json={"id": "1-0"}))
    token = criar_token(role="cinefilo")

    resposta = client.post("/auth/logout", headers=auth_headers(token))

    assert resposta.status_code == 204
    assert rota_mock.called
    assert b'"acao":"logout"' in rota_mock.calls.last.request.content


@respx.mock
def test_consultar_logs_usuario_comum_recebe_403_sem_proxy_de_consulta(client):
    # POST mockado porque o próprio 403 do require_admin já dispara um
    # evento de auditoria ("acesso_negado:admin") — é a GET (o proxy de
    # consulta em si) que não deve ser chamada, já que o catálogo barra
    # antes de repassar pro log-service.
    respx.post(f"{LOG_SERVICE_URL}/logs").mock(return_value=Response(201, json={"id": "1-0"}))
    rota_consulta = respx.get(f"{LOG_SERVICE_URL}/logs")
    token = criar_token(role="nerd")

    resposta = client.get("/admin/logs", headers=auth_headers(token))

    assert resposta.status_code == 403
    assert not rota_consulta.called


@respx.mock
def test_consultar_logs_como_admin_repassa_resposta_do_log_service(client):
    eventos = [
        {"usuario_id": 1, "acao": "login", "timestamp": "2026-01-01T00:00:00+00:00", "ip": None}
    ]
    rota_mock = respx.get(f"{LOG_SERVICE_URL}/logs").mock(return_value=Response(200, json=eventos))
    token_admin = criar_token(role="admin")

    resposta = client.get("/admin/logs?limit=10", headers=auth_headers(token_admin))

    assert resposta.status_code == 200
    assert resposta.json() == eventos
    # repassa o token original pro log-service, que confere de novo (mesma
    # checagem de role admin da atividade 4)
    assert rota_mock.calls.last.request.headers["Authorization"] == auth_headers(token_admin)["Authorization"]
    assert rota_mock.calls.last.request.url.params["limit"] == "10"
