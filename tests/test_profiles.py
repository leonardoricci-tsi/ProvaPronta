import respx
from httpx import Response

from app.config import get_settings
from app.models import Perfil
from tests.conftest import auth_headers, criar_token

AUTH_URL = get_settings().auth_service_url


def test_perfil_sem_edicao_vem_vazio_com_nome_do_auth_service(client, auth_service):
    token = criar_token(usuario_id=501, role="cinefilo")

    resposta = client.get("/profiles/501", headers=auth_headers(token))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["nome"] == "Usuário 501"
    assert corpo["bio"] == ""
    assert corpo["foto_url"] is None
    assert corpo["eh_meu"] is True


def test_perfil_de_usuario_inexistente_da_404(client):
    with respx.mock:
        respx.get(f"{AUTH_URL}/auth/users/999").mock(
            return_value=Response(404, json={"detail": "Usuário não encontrado"})
        )
        token = criar_token(usuario_id=504)

        resposta = client.get("/profiles/999", headers=auth_headers(token))

    assert resposta.status_code == 404


def test_perfil_exige_login(client):
    assert client.get("/profiles/1").status_code == 401


def test_dono_edita_a_propria_bio(client, auth_service):
    token = criar_token(usuario_id=505, role="cinefilo")

    resposta = client.patch("/profiles/505", json={"bio": "Professora de Biologia"}, headers=auth_headers(token))

    assert resposta.status_code == 200
    assert resposta.json()["bio"] == "Professora de Biologia"
    releitura = client.get("/profiles/505", headers=auth_headers(token))
    assert releitura.json()["bio"] == "Professora de Biologia"


def test_nao_edita_perfil_de_outro_usuario(client, auth_service, db_session):
    token_intruso = criar_token(usuario_id=506, role="nerd")

    resposta = client.patch(
        "/profiles/507", json={"bio": "hackeado"}, headers=auth_headers(token_intruso)
    )

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Você só pode editar o próprio perfil"
    assert db_session.get(Perfil, 507) is None


def test_admin_tambem_nao_edita_perfil_de_outro(client, auth_service):
    token_admin = criar_token(usuario_id=508, role="admin")

    resposta = client.patch("/profiles/509", json={"bio": "x"}, headers=auth_headers(token_admin))

    assert resposta.status_code == 403


def test_usuario_id_no_corpo_e_ignorado(client, auth_service, db_session):
    """Mandar o ID de outra pessoa no corpo não muda de quem é o perfil
    editado — o dono vem do JWT (e da URL, conferida contra o JWT)."""
    token = criar_token(usuario_id=510, role="nerd")

    resposta = client.patch(
        "/profiles/510",
        json={"bio": "minha bio", "usuario_id": 511},
        headers=auth_headers(token),
    )

    assert resposta.status_code == 200
    assert db_session.get(Perfil, 510).bio == "minha bio"
    assert db_session.get(Perfil, 511) is None


def test_bio_acima_de_280_caracteres_e_recusada(client, auth_service):
    token = criar_token(usuario_id=512)

    resposta = client.patch("/profiles/512", json={"bio": "a" * 281}, headers=auth_headers(token))

    assert resposta.status_code == 422


def test_tentativa_negada_vai_pro_log_de_auditoria(client, auth_service):
    token_intruso = criar_token(usuario_id=513, role="nerd")

    client.patch("/profiles/514", json={"bio": "x"}, headers=auth_headers(token_intruso))

    rota_log = auth_service.routes[1]
    assert b"acesso_negado:perfil:514" in rota_log.calls.last.request.content


def test_editar_bio_vai_pro_log_de_auditoria(client, auth_service):
    token = criar_token(usuario_id=515)

    client.patch("/profiles/515", json={"bio": "oi"}, headers=auth_headers(token))

    rota_log = auth_service.routes[1]
    assert b"atualizar_perfil" in rota_log.calls.last.request.content


def test_foto_vira_url_temporaria_na_leitura(client, auth_service, db_session, monkeypatch):
    """O banco guarda só a chave; a URL pré-assinada é montada na hora."""
    from app.services import storage

    settings = get_settings()
    monkeypatch.setattr(storage, "_client_publico", None)
    monkeypatch.setattr(settings, "s3_access_key", "GK" + "0" * 32)
    monkeypatch.setattr(settings, "s3_secret_key", "f" * 64)
    monkeypatch.setattr(settings, "s3_public_url", "http://fotos.exemplo.com:3900")
    db_session.add(Perfil(usuario_id=516, foto_key="perfis/516/abc.jpg"))
    db_session.commit()
    token = criar_token(usuario_id=517)

    resposta = client.get("/profiles/516", headers=auth_headers(token))

    foto_url = resposta.json()["foto_url"]
    assert foto_url.startswith(f"http://fotos.exemplo.com:3900/{settings.s3_bucket}/perfis/516/abc.jpg?")
    assert "X-Amz-Signature=" in foto_url
