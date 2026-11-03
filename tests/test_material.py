from app.models import Prova
from app.services import storage
from tests.conftest import auth_headers, criar_token

PDF = b"%PDF-1.4\n1 0 obj << >> endobj\n%%EOF\n"


def criar_prova(client, token):
    turma = client.post(
        "/turmas", json={"nome": "1º A", "disciplina": "Biologia", "ano_letivo": 2026}, headers=auth_headers(token)
    ).json()
    resposta = client.post("/provas", json={"turma_id": turma["id"], "titulo": "P1"}, headers=auth_headers(token))
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def enviar(client, prova_id, token, conteudo=PDF, nome="apostila.pdf"):
    return client.post(
        f"/provas/{prova_id}/material",
        files={"arquivo": (nome, conteudo, "application/pdf")},
        headers=auth_headers(token),
    )


def test_pdf_vai_pro_garage_e_so_a_chave_fica_na_prova(client, auth_service, garage_falso, db_session):
    token = criar_token(usuario_id=901)
    prova = criar_prova(client, token)

    resposta = enviar(client, prova["id"], token)

    assert resposta.status_code == 200
    assert resposta.json()["material_nome"] == "apostila.pdf"
    chave = db_session.get(Prova, prova["id"]).material_key
    assert chave.startswith(f"materiais/901/{prova['id']}/") and chave.endswith(".pdf")
    assert garage_falso[chave] == (PDF, "application/pdf")

    link = client.get(f"/provas/{prova['id']}/material", headers=auth_headers(token)).json()
    assert link == {"nome": "apostila.pdf", "url": f"http://garage.teste/{chave}?assinada"}


def test_trocar_o_pdf_apaga_o_antigo(client, auth_service, garage_falso, db_session):
    token = criar_token()
    prova = criar_prova(client, token)
    enviar(client, prova["id"], token)
    primeira = db_session.get(Prova, prova["id"]).material_key

    enviar(client, prova["id"], token, nome="livro.pdf")

    segunda = db_session.get(Prova, prova["id"]).material_key
    assert primeira != segunda
    assert list(garage_falso) == [segunda]


def test_arquivo_que_nao_e_pdf_e_recusado_mesmo_com_extensao_pdf(client, auth_service, garage_falso):
    token = criar_token()
    prova = criar_prova(client, token)

    resposta = enviar(client, prova["id"], token, conteudo=b"MZ\x90\x00executavel", nome="virus.pdf")

    assert resposta.status_code == 415
    assert garage_falso == {}


def test_pdf_acima_de_10_mb_e_recusado(client, auth_service, garage_falso, monkeypatch):
    from app.routers import provas

    monkeypatch.setattr(provas, "TAMANHO_MAXIMO_MATERIAL", 10)
    token = criar_token()
    prova = criar_prova(client, token)

    assert enviar(client, prova["id"], token).status_code == 413
    assert garage_falso == {}


def test_material_da_prova_de_outro_da_404(client, auth_service, garage_falso):
    token_dono, token_intruso = criar_token(), criar_token()
    prova = criar_prova(client, token_dono)
    enviar(client, prova["id"], token_dono)
    url = f"/provas/{prova['id']}/material"

    assert client.get(url, headers=auth_headers(token_intruso)).status_code == 404
    assert enviar(client, prova["id"], token_intruso).status_code == 404
    assert client.delete(url, headers=auth_headers(token_intruso)).status_code == 404
    assert len(garage_falso) == 1


def test_remover_material_e_remover_prova_limpam_o_garage(client, auth_service, garage_falso):
    token = criar_token()
    prova_a, prova_b = criar_prova(client, token), criar_prova(client, token)
    enviar(client, prova_a["id"], token)
    enviar(client, prova_b["id"], token)

    assert client.delete(f"/provas/{prova_a['id']}/material", headers=auth_headers(token)).status_code == 204
    assert client.get(f"/provas/{prova_a['id']}/material", headers=auth_headers(token)).status_code == 404
    assert client.delete(f"/provas/{prova_b['id']}", headers=auth_headers(token)).status_code == 204
    assert garage_falso == {}


def test_garage_fora_do_ar_da_502_e_nao_grava_na_prova(client, auth_service, monkeypatch, db_session):
    def falhar(*_args):
        raise storage.StorageUnavailable("Armazenamento de arquivos indisponível no momento")

    monkeypatch.setattr(storage, "enviar_objeto", falhar)
    token = criar_token()
    prova = criar_prova(client, token)

    assert enviar(client, prova["id"], token).status_code == 502
    assert db_session.get(Prova, prova["id"]).material_key is None


def test_envio_de_material_vai_pro_log(client, auth_service, garage_falso):
    token = criar_token(usuario_id=910)
    prova = criar_prova(client, token)

    enviar(client, prova["id"], token)

    corpo = auth_service.routes[1].calls.last.request.content
    assert f"material_enviado:prova:{prova['id']}".encode() in corpo
    assert b'"usuario_id":910' in corpo
