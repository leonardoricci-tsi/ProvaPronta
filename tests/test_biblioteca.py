"""Biblioteca de materiais: PDFs em pastas, e gerar questões a partir de
uma pasta inteira, de um PDF ou de vários."""

import json

from tests.conftest import auth_headers, criar_token
from tests.test_gerar_questoes import QUESTAO_BOA, ia, pdf_com_texto, resposta_da_ia  # noqa: F401
from tests.test_provas import criar_prova, criar_turma

TEXTO_MAT_1 = (
    "Conjuntos numéricos. Os números naturais começam no zero e seguem 1, 2, 3. Os inteiros "
    "incluem os negativos. Os racionais podem ser escritos como fração de dois inteiros, com "
    "denominador diferente de zero. Toda dízima periódica é um número racional."
)
TEXTO_MAT_2 = (
    "Funções do primeiro grau. A função afim tem a forma f(x) = ax + b, com a diferente de zero. "
    "O coeficiente angular a indica a inclinação da reta; se a é positivo, a função é crescente. "
    "O coeficiente linear b é o ponto onde a reta corta o eixo y."
)


def criar_pasta(client, token, nome="1º ano — Matemática — 1º bimestre"):
    resposta = client.post("/pastas", json={"nome": nome}, headers=auth_headers(token))
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def enviar_pdfs(client, token, pasta_id, *arquivos):
    files = [("arquivos", (nome, conteudo, "application/pdf")) for nome, conteudo in arquivos]
    return client.post(f"/pastas/{pasta_id}/materiais", files=files, headers=auth_headers(token))


def test_pasta_com_varios_pdfs_de_uma_vez(client, auth_service, garage_falso):
    token = criar_token(role="professor_pro")
    pasta = criar_pasta(client, token)

    resposta = enviar_pdfs(
        client,
        token,
        pasta["id"],
        ("conjuntos.pdf", pdf_com_texto(TEXTO_MAT_1)),
        ("funcoes.pdf", pdf_com_texto(TEXTO_MAT_2)),
    )

    assert resposta.status_code == 201, resposta.text
    assert [m["nome"] for m in resposta.json()] == ["conjuntos.pdf", "funcoes.pdf"]
    assert all(chave.startswith("biblioteca/") for chave in garage_falso)
    lista = client.get("/pastas", headers=auth_headers(token)).json()
    assert [(p["nome"], p["total_materiais"]) for p in lista] == [("1º ano — Matemática — 1º bimestre", 2)]
    link = client.get(f"/materiais/{resposta.json()[0]['id']}/link", headers=auth_headers(token)).json()
    assert link["nome"] == "conjuntos.pdf" and "assinada" in link["url"]


def test_um_arquivo_invalido_cancela_o_envio_inteiro(client, auth_service, garage_falso):
    token = criar_token(role="professor_pro")
    pasta = criar_pasta(client, token)

    resposta = enviar_pdfs(
        client, token, pasta["id"], ("bom.pdf", pdf_com_texto(TEXTO_MAT_1)), ("falso.pdf", b"nao sou pdf")
    )

    assert resposta.status_code == 415
    assert garage_falso == {}
    assert client.get(f"/pastas/{pasta['id']}", headers=auth_headers(token)).json()["total_materiais"] == 0


def test_free_guarda_ate_3_pdfs(client, auth_service, garage_falso):
    token = criar_token(role="professor")
    pasta = criar_pasta(client, token)
    pdf = pdf_com_texto(TEXTO_MAT_1)
    assert enviar_pdfs(client, token, pasta["id"], ("a.pdf", pdf), ("b.pdf", pdf)).status_code == 201

    resposta = enviar_pdfs(client, token, pasta["id"], ("c.pdf", pdf), ("d.pdf", pdf))

    assert resposta.status_code == 403
    corpos = b"\n".join(c.request.content for c in auth_service.routes[1].calls)
    assert b"acesso_negado:limite_free:materiais" in corpos
    assert enviar_pdfs(client, token, pasta["id"], ("c.pdf", pdf)).status_code == 201


def test_pasta_e_pdf_de_outro_dao_404(client, auth_service, garage_falso):
    dono = criar_token(role="professor_pro")
    pasta = criar_pasta(client, dono)
    material = enviar_pdfs(client, dono, pasta["id"], ("a.pdf", pdf_com_texto(TEXTO_MAT_1))).json()[0]
    intruso = auth_headers(criar_token(role="professor_pro"))

    assert client.get(f"/pastas/{pasta['id']}", headers=intruso).status_code == 404
    assert client.patch(f"/pastas/{pasta['id']}", json={"nome": "x"}, headers=intruso).status_code == 404
    assert client.delete(f"/pastas/{pasta['id']}", headers=intruso).status_code == 404
    assert enviar_pdfs(client, criar_token(), pasta["id"], ("b.pdf", pdf_com_texto(TEXTO_MAT_1))).status_code == 404
    assert client.get(f"/materiais/{material['id']}/link", headers=intruso).status_code == 404
    assert client.delete(f"/materiais/{material['id']}", headers=intruso).status_code == 404
    assert client.get("/pastas", headers=intruso).json() == []


def test_apagar_pasta_apaga_os_pdfs_no_garage(client, auth_service, garage_falso):
    token = criar_token(role="professor_pro")
    pasta = criar_pasta(client, token)
    enviar_pdfs(client, token, pasta["id"], ("a.pdf", pdf_com_texto(TEXTO_MAT_1)), ("b.pdf", pdf_com_texto(TEXTO_MAT_2)))
    assert len(garage_falso) == 2

    assert client.delete(f"/pastas/{pasta['id']}", headers=auth_headers(token)).status_code == 204

    assert garage_falso == {}
    assert client.get("/pastas", headers=auth_headers(token)).json() == []


def _prova_sem_pdf(client, token):
    return criar_prova(client, token, criar_turma(client, token)["id"], questoes=[])


def test_gera_a_partir_de_uma_pasta_inteira(client, auth_service, garage_falso, ia):
    ia.mock(return_value=resposta_da_ia([QUESTAO_BOA]))
    token = criar_token(role="professor_pro")
    pasta = criar_pasta(client, token)
    enviar_pdfs(client, token, pasta["id"], ("conjuntos.pdf", pdf_com_texto(TEXTO_MAT_1)), ("funcoes.pdf", pdf_com_texto(TEXTO_MAT_2)))
    prova = _prova_sem_pdf(client, token)

    resposta = client.post(
        f"/provas/{prova['id']}/gerar-questoes", json={"pasta_ids": [pasta["id"]]}, headers=auth_headers(token)
    )

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["fonte"] == "2 PDFs"
    assert sorted(resposta.json()["fontes"]) == ["conjuntos.pdf", "funcoes.pdf"]
    # Os dois PDFs entram no material mandado pra IA, cada um com o nome.
    material = json.loads(ia.calls.last.request.content)["messages"][1]["content"]
    assert "[conjuntos.pdf]" in material and "[funcoes.pdf]" in material
    assert "racionais" in material and "coeficiente angular" in material


def test_gera_a_partir_de_pdfs_escolhidos_um_a_um(client, auth_service, garage_falso, ia):
    ia.mock(return_value=resposta_da_ia([QUESTAO_BOA]))
    token = criar_token(role="professor_pro")
    pasta_1 = criar_pasta(client, token, "Matemática — 1º bimestre")
    pasta_2 = criar_pasta(client, token, "Matemática — 2º bimestre")
    m1 = enviar_pdfs(client, token, pasta_1["id"], ("conjuntos.pdf", pdf_com_texto(TEXTO_MAT_1))).json()[0]
    enviar_pdfs(client, token, pasta_1["id"], ("outro.pdf", pdf_com_texto(TEXTO_MAT_2)))
    m3 = enviar_pdfs(client, token, pasta_2["id"], ("funcoes.pdf", pdf_com_texto(TEXTO_MAT_2))).json()[0]
    prova = _prova_sem_pdf(client, token)

    resposta = client.post(
        f"/provas/{prova['id']}/gerar-questoes",
        json={"material_ids": [m1["id"], m3["id"]]},
        headers=auth_headers(token),
    )

    assert resposta.status_code == 200, resposta.text
    assert sorted(resposta.json()["fontes"]) == ["conjuntos.pdf", "funcoes.pdf"]


def test_gera_com_um_unico_pdf_da_biblioteca(client, auth_service, garage_falso, ia):
    ia.mock(return_value=resposta_da_ia([QUESTAO_BOA]))
    token = criar_token(role="professor_pro")
    pasta = criar_pasta(client, token)
    material = enviar_pdfs(client, token, pasta["id"], ("conjuntos.pdf", pdf_com_texto(TEXTO_MAT_1))).json()[0]
    prova = _prova_sem_pdf(client, token)

    resposta = client.post(
        f"/provas/{prova['id']}/gerar-questoes", json={"material_ids": [material["id"]]}, headers=auth_headers(token)
    )

    assert (resposta.status_code, resposta.json()["fonte"]) == (200, "conjuntos.pdf")
    material_enviado = json.loads(ia.calls.last.request.content)["messages"][1]["content"]
    # Com um PDF só, sem cabeçalho de nome.
    assert "[conjuntos.pdf]" not in material_enviado


def test_nao_gera_com_pdf_ou_pasta_de_outro(client, auth_service, garage_falso, ia):
    dono = criar_token(role="professor_pro")
    pasta = criar_pasta(client, dono)
    material = enviar_pdfs(client, dono, pasta["id"], ("a.pdf", pdf_com_texto(TEXTO_MAT_1))).json()[0]
    intruso = criar_token(role="professor_pro")
    prova = _prova_sem_pdf(client, intruso)

    for corpo in ({"material_ids": [material["id"]]}, {"pasta_ids": [pasta["id"]]}):
        resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", json=corpo, headers=auth_headers(intruso))
        assert resposta.status_code == 404
    assert not ia.called


def test_pasta_vazia_da_409(client, auth_service, garage_falso, ia):
    token = criar_token(role="professor_pro")
    pasta = criar_pasta(client, token)
    prova = _prova_sem_pdf(client, token)

    resposta = client.post(
        f"/provas/{prova['id']}/gerar-questoes", json={"pasta_ids": [pasta["id"]]}, headers=auth_headers(token)
    )

    assert resposta.status_code == 409
    assert not ia.called


def test_texto_e_repartido_entre_os_pdfs():
    from app.services.gerador_questoes import _repartir

    assert _repartir(["a" * 100, "b" * 10, "c" * 100], 60) == ["a" * 25, "b" * 10, "c" * 25]
    assert _repartir(["a" * 5, "", "b" * 5], 100) == ["a" * 5, "", "b" * 5]
