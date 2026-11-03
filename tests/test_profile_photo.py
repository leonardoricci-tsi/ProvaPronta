import io

import pytest
from PIL import Image

from app.models import Perfil
from app.services import imagem, storage
from tests.conftest import auth_headers, criar_token


def gerar_imagem(formato="PNG", tamanho=(64, 64), exif=None) -> bytes:
    saida = io.BytesIO()
    kwargs = {"exif": exif} if exif is not None else {}
    Image.new("RGB", tamanho, "red").save(saida, format=formato, **kwargs)
    return saida.getvalue()


def enviar(client, usuario_id, token, conteudo, nome="foto.png", content_type="image/png"):
    return client.post(
        f"/profiles/{usuario_id}/foto",
        files={"arquivo": (nome, conteudo, content_type)},
        headers=auth_headers(token),
    )


# --- rota ---


def test_upload_grava_arquivo_no_garage_e_so_a_chave_no_banco(
    client, auth_service, garage_falso, db_session
):
    token = criar_token(usuario_id=601)

    resposta = enviar(client, 601, token, gerar_imagem("PNG"))

    assert resposta.status_code == 200, resposta.text
    perfil = db_session.get(Perfil, 601)
    assert perfil.foto_key.startswith("perfis/601/") and perfil.foto_key.endswith(".png")
    assert list(garage_falso) == [perfil.foto_key]
    assert garage_falso[perfil.foto_key][1] == "image/png"
    assert resposta.json()["foto_url"] == f"http://garage.teste/{perfil.foto_key}?assinada"


def test_nao_envia_foto_pro_perfil_de_outro(client, auth_service, garage_falso, db_session):
    token_intruso = criar_token(usuario_id=602)

    resposta = enviar(client, 603, token_intruso, gerar_imagem())

    assert resposta.status_code == 403
    assert garage_falso == {}
    assert db_session.get(Perfil, 603) is None


def test_trocar_foto_apaga_a_antiga_do_garage(client, auth_service, garage_falso, db_session):
    token = criar_token(usuario_id=604)
    enviar(client, 604, token, gerar_imagem())
    chave_antiga = db_session.get(Perfil, 604).foto_key

    enviar(client, 604, token, gerar_imagem("JPEG"), nome="nova.jpg", content_type="image/jpeg")

    chave_nova = db_session.get(Perfil, 604).foto_key
    assert chave_nova != chave_antiga and chave_nova.endswith(".jpg")
    assert list(garage_falso) == [chave_nova]


def test_arquivo_que_nao_e_imagem_e_recusado_mesmo_com_content_type_de_imagem(
    client, auth_service, garage_falso
):
    token = criar_token(usuario_id=605)

    resposta = enviar(client, 605, token, b"<?php system($_GET['c']); ?>", nome="foto.png")

    assert resposta.status_code == 415
    assert garage_falso == {}


def test_gif_e_recusado(client, auth_service, garage_falso):
    token = criar_token(usuario_id=606)

    resposta = enviar(client, 606, token, gerar_imagem("GIF"), nome="a.gif", content_type="image/gif")

    assert resposta.status_code == 415


def test_arquivo_acima_de_2mb_e_recusado(client, auth_service, garage_falso):
    token = criar_token(usuario_id=607)

    resposta = enviar(client, 607, token, b"\x89PNG" + b"0" * imagem.TAMANHO_MAXIMO_BYTES)

    assert resposta.status_code == 413
    assert garage_falso == {}


def test_garage_fora_do_ar_da_502_e_nao_grava_no_banco(client, auth_service, monkeypatch, db_session):
    def falhar(*_):
        raise storage.StorageUnavailable("Armazenamento de arquivos indisponível no momento")

    monkeypatch.setattr(storage, "enviar_objeto", falhar)
    token = criar_token(usuario_id=608)

    resposta = enviar(client, 608, token, gerar_imagem())

    assert resposta.status_code == 502
    assert db_session.get(Perfil, 608) is None


def test_upload_vai_pro_log_de_auditoria(client, auth_service, garage_falso):
    token = criar_token(usuario_id=609)

    enviar(client, 609, token, gerar_imagem())

    assert b"upload_foto_perfil" in auth_service.routes[1].calls.last.request.content


# --- processamento da imagem ---


def test_foto_grande_e_reduzida():
    conteudo, extensao, content_type = imagem.processar_foto(gerar_imagem("JPEG", (3000, 2000)))

    assert (extensao, content_type) == ("jpg", "image/jpeg")
    assert max(Image.open(io.BytesIO(conteudo)).size) == imagem.LADO_MAXIMO


def test_exif_e_descartado():
    exif = Image.Exif()
    exif[0x010F] = "CameraQueEntregaOnde"  # Make
    original = gerar_imagem("JPEG", exif=exif.tobytes())
    assert b"CameraQueEntregaOnde" in original

    conteudo, _, _ = imagem.processar_foto(original)

    assert b"CameraQueEntregaOnde" not in conteudo


def test_decompression_bomb_e_recusada(monkeypatch):
    monkeypatch.setattr(imagem, "PIXELS_MAXIMOS", 100)

    with pytest.raises(imagem.ImagemInvalida):
        imagem.processar_foto(gerar_imagem("PNG", (20, 20)))


def test_imagem_corrompida_e_recusada():
    truncada = gerar_imagem("PNG", (200, 200))[:60]

    with pytest.raises(imagem.ImagemInvalida):
        imagem.processar_foto(truncada)
