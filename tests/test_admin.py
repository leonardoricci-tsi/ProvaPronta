import respx
from httpx import Response

from tests.conftest import auth_headers, criar_token


def test_usuario_comum_nao_acessa_rota_admin(client):
    token = criar_token(role="nerd")

    resposta = client.get("/admin/logs", headers=auth_headers(token))

    assert resposta.status_code == 403


# --- admin: promover/rebaixar papel de usuário (proxy pro auth-service) ---


@respx.mock
def test_admin_lista_usuarios(client):
    from app.config import get_settings

    auth_url = get_settings().auth_service_url
    respx.get(f"{auth_url}/auth/admin/users").mock(
        return_value=Response(
            200,
            json=[
                {
                    "id": 1,
                    "nome": "Ana",
                    "email": "ana@example.com",
                    "role": "cinefilo",
                    "criado_em": "2026-01-01T00:00:00",
                }
            ],
        )
    )
    token = criar_token(role="admin")

    resposta = client.get("/auth/admin/users", headers=auth_headers(token))

    assert resposta.status_code == 200
    assert resposta.json()[0]["role"] == "cinefilo"


@respx.mock
def test_admin_promove_usuario(client):
    from app.config import get_settings

    auth_url = get_settings().auth_service_url
    rota_mock = respx.patch(f"{auth_url}/auth/admin/users/1/role").mock(
        return_value=Response(
            200,
            json={
                "id": 1,
                "nome": "Ana",
                "email": "ana@example.com",
                "role": "stalker_do_tomhanks",
                "criado_em": "2026-01-01T00:00:00",
            },
        )
    )
    token = criar_token(role="admin")

    resposta = client.patch(
        "/auth/admin/users/1/role",
        json={"role": "stalker_do_tomhanks"},
        headers=auth_headers(token),
    )

    assert resposta.status_code == 200
    assert resposta.json()["role"] == "stalker_do_tomhanks"
    assert rota_mock.calls.last.request.headers["Authorization"] == auth_headers(token)["Authorization"]
