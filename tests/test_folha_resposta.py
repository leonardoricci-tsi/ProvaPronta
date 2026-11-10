"""Folha de respostas (uma página por aluno, com QR e marcas) e caderno da
prova em PDF."""

import io

from pypdf import PdfReader

from app.services import folha_resposta as fr
from tests.conftest import auth_headers, criar_token
from tests.test_provas import QUESTOES, criar_prova, criar_turma


def turma_com_alunos(client, token, nomes=("Ana Souza", "Bruno Lima", "Carla Dias")):
    turma = criar_turma(client, token)
    for numero, nome in enumerate(nomes, start=1):
        resposta = client.post(
            f"/turmas/{turma['id']}/alunos",
            json={"nome": nome, "numero_chamada": numero},
            headers=auth_headers(token),
        )
        assert resposta.status_code == 201
    return turma


def paginas(conteudo: bytes) -> list[str]:
    return [p.extract_text() for p in PdfReader(io.BytesIO(conteudo)).pages]


def test_uma_folha_por_aluno_com_nome_e_prova(client, auth_service):
    token = criar_token()
    turma = turma_com_alunos(client, token)
    prova = criar_prova(client, token, turma["id"], titulo="P1 — Citologia")

    resposta = client.get(f"/provas/{prova['id']}/folhas-resposta.pdf", headers=auth_headers(token))

    assert resposta.status_code == 200
    assert resposta.headers["content-type"] == "application/pdf"
    textos = paginas(resposta.content)
    assert len(textos) == 3
    for texto, nome in zip(textos, ("1. Ana Souza", "2. Bruno Lima", "3. Carla Dias")):
        assert "Folha de respostas" in texto and "P1 — Citologia" in texto and nome in texto
    corpos = b"\n".join(c.request.content for c in auth_service.routes[1].calls)
    assert f"folhas_geradas:prova:{prova['id']}:3".encode() in corpos


def test_caderno_tem_as_questoes_sem_gabarito(client, auth_service):
    token = criar_token()
    prova = criar_prova(client, token, criar_turma(client, token)["id"])

    resposta = client.get(f"/provas/{prova['id']}/caderno.pdf", headers=auth_headers(token))

    assert resposta.status_code == 200
    texto = " ".join(paginas(resposta.content))
    assert "1. Qual organela faz a respiração celular?" in texto
    assert "B) Mitocôndria" in texto and "C) Amido" in texto
    assert "gabarito" not in texto.lower()


def test_sem_alunos_ou_sem_questoes_da_409(client, auth_service):
    token = criar_token()
    sem_alunos = criar_prova(client, token, criar_turma(client, token)["id"])
    assert client.get(f"/provas/{sem_alunos['id']}/folhas-resposta.pdf", headers=auth_headers(token)).status_code == 409

    sem_questoes = criar_prova(client, token, turma_com_alunos(client, token)["id"], questoes=[])
    for rota in ("folhas-resposta.pdf", "caderno.pdf"):
        assert client.get(f"/provas/{sem_questoes['id']}/{rota}", headers=auth_headers(token)).status_code == 409


def test_prova_de_outro_da_404(client, auth_service):
    dono = criar_token()
    prova = criar_prova(client, dono, turma_com_alunos(client, dono)["id"])
    intruso = auth_headers(criar_token())

    for rota in ("folhas-resposta.pdf", "caderno.pdf"):
        assert client.get(f"/provas/{prova['id']}/{rota}", headers=intruso).status_code == 404


def test_texto_do_professor_nao_quebra_o_caderno(client, auth_service):
    token = criar_token()
    questoes = [{**QUESTOES[0], "enunciado": "Se a < b e b > c, então <b>?</b> & mais"}]
    prova = criar_prova(client, token, criar_turma(client, token)["id"], questoes=questoes)

    resposta = client.get(f"/provas/{prova['id']}/caderno.pdf", headers=auth_headers(token))

    assert resposta.status_code == 200
    assert "Se a < b e b > c, então <b>?</b> & mais" in " ".join(paginas(resposta.content))


def test_conteudo_do_qr_vai_e_volta_e_e_assinado():
    conteudo = fr.conteudo_qr(12, 345)
    assert conteudo.startswith("PP2:12:345:") and len(conteudo.split(":")[3]) == 12
    assert fr.ler_conteudo_qr(conteudo) == (12, 345)
    assinatura = conteudo.split(":")[3]
    # Trocar o aluno (ou a prova) sem saber o segredo não passa.
    for invalido in (
        f"PP2:12:346:{assinatura}",
        f"PP2:13:345:{assinatura}",
        "PP2:12:345:000000000000",
        "PP1:12:345",  # folha antiga, sem assinatura
        "PP2:12:345",
        "PP2:a:3:" + assinatura,
        "https://exemplo.com",
        "",
    ):
        assert fr.ler_conteudo_qr(invalido) is None


def test_geometria_de_100_questoes_cabe_e_nao_encosta_nas_marcas_nem_no_qr():
    """A correção por foto depende destas posições: nenhuma bolinha pode sair
    da folha, encostar numa marca de canto ou cair em cima do QR."""
    r = fr.BOLINHA_RAIO
    marcas = [(cx - fr.MARCA_LADO / 2, cy - fr.MARCA_LADO / 2, fr.MARCA_LADO) for cx, cy in fr.centros_das_marcas()]
    centros = [fr.centro_da_bolinha(q, a) for q in range(100) for a in range(5)]

    for x, y in centros:
        assert r < x < fr.LARGURA - r and r < y < fr.ALTURA - r
        for mx, my, lado in marcas:
            assert not (mx - r < x < mx + lado + r and my - r < y < my + lado + r)
        assert not (fr.QR_X - r < x < fr.QR_X + fr.QR_LADO + r and fr.QR_Y - r < y < fr.QR_Y + fr.QR_LADO + r)
    # Bolinhas vizinhas não se tocam.
    (x0, y0), (x1, _), (_, y2) = fr.centro_da_bolinha(0, 0), fr.centro_da_bolinha(0, 1), fr.centro_da_bolinha(1, 0)
    assert x1 - x0 > 2 * r and y0 - y2 > 2 * r
    # Colunas não se sobrepõem (a última bolinha de uma vem antes do número da próxima).
    assert fr.centro_da_bolinha(0, 4)[0] + r < fr.centro_da_bolinha(25, 0)[0] - fr.DESLOCAMENTO_1A_BOLINHA


def test_folha_com_100_questoes_gera_uma_pagina_por_aluno():
    dados = fr.DadosFolha(
        prova_id=1,
        titulo="Simulado " + "muito longo " * 20,
        turma="3º A — Matemática",
        data_aplicacao="20/11/2026",
        aluno_id=7,
        aluno_nome="Maria " + "da Silva " * 15,
        numero_chamada=7,
        alternativas_por_questao=[5] * 100,
    )
    textos = paginas(fr.gerar_folhas([dados, dados]))
    assert len(textos) == 2
    assert "100" in textos[0]
