"""Gerar questões a partir do PDF da apostila (plano Pro). A IA é mockada
(respx): o que se testa é o que a API manda, o que ela aceita de volta e
quem pode usar."""

import json

import pytest
from httpx import Response

from app.config import get_settings
from tests.conftest import auth_headers, criar_token
from tests.test_provas import criar_prova, criar_turma

TEXTO_APOSTILA = (
    "Citologia. A célula é a unidade básica da vida. A mitocôndria é a organela "
    "responsável pela respiração celular, que produz energia na forma de ATP. "
    "A membrana plasmática é formada por uma bicamada de fosfolipídios com proteínas. "
    "Os ribossomos fazem a síntese de proteínas. A parede celular está presente na "
    "célula vegetal e ausente na célula animal. O núcleo guarda o material genético."
)


def pdf_com_texto(texto: str) -> bytes:
    """PDF mínimo e válido, com o texto numa página (Helvetica)."""
    linhas = [texto[i : i + 80] for i in range(0, len(texto), 80)]
    ops = ["BT", "/F1 11 Tf"]
    y = 780
    for linha in linhas:
        seguro = linha.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        ops.append(f"1 0 0 1 50 {y} Tm ({seguro}) Tj")
        y -= 16
    ops.append("ET")
    stream = "\n".join(ops).encode("latin-1")
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    saida = b"%PDF-1.4\n"
    posicoes = []
    for numero, obj in enumerate(objs, 1):
        posicoes.append(len(saida))
        saida += b"%d 0 obj\n" % numero + obj + b"\nendobj\n"
    xref = len(saida)
    saida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    saida += b"".join(b"%010d 00000 n \n" % p for p in posicoes)
    saida += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    return saida


def resposta_da_ia(questoes: list[dict]) -> Response:
    conteudo = json.dumps({"questoes": questoes}, ensure_ascii=False)
    return Response(200, json={"choices": [{"message": {"role": "assistant", "content": conteudo}}]})


QUESTAO_BOA = {
    "enunciado": "Qual organela faz a respiração celular?",
    "alternativas": ["Ribossomo", "Mitocôndria", "Lisossomo", "Golgi"],
    "resposta_correta": 1,
    "assunto": "Organelas",
}


@pytest.fixture()
def ia(monkeypatch, auth_service):
    """Liga a geração (chave falsa) e mocka o /chat/completions do provedor.
    Reaproveita o respx do `auth_service` (um mock ativo por vez)."""
    settings = get_settings()
    monkeypatch.setattr(settings, "llm_api_key", "chave-de-teste")
    monkeypatch.setattr(settings, "llm_base_url", "https://ia.teste/v1")
    return auth_service.post("https://ia.teste/v1/chat/completions", name="ia")


def prova_com_pdf(client, token, conteudo: bytes | None = None):
    turma = criar_turma(client, token)
    prova = criar_prova(client, token, turma["id"], questoes=[])
    resposta = client.post(
        f"/provas/{prova['id']}/material",
        files={"arquivo": ("apostila.pdf", conteudo or pdf_com_texto(TEXTO_APOSTILA), "application/pdf")},
        headers=auth_headers(token),
    )
    assert resposta.status_code == 200, resposta.text
    return prova


def test_gera_sugestoes_a_partir_do_texto_do_pdf(client, garage_falso, ia, auth_service):
    ia.mock(return_value=resposta_da_ia([QUESTAO_BOA]))
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    resposta = client.post(
        f"/provas/{prova['id']}/gerar-questoes", json={"quantidade": 3}, headers=auth_headers(token)
    )

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["fonte"] == "apostila.pdf"
    assert corpo["questoes"] == [QUESTAO_BOA]
    # O que foi pro provedor: o modelo configurado, JSON obrigatório e o
    # texto extraído do PDF — com a quantidade e a disciplina da turma.
    pedido = json.loads(ia.calls.last.request.content)
    assert ia.calls.last.request.headers["authorization"] == "Bearer chave-de-teste"
    assert pedido["model"] == get_settings().llm_model
    assert pedido["response_format"] == {"type": "json_object"}
    mensagem = pedido["messages"][1]["content"]
    assert "Crie 3 questões" in mensagem and "Biologia" in mensagem and "mitocôndria" in mensagem
    # Sugestão não é gravada: a prova continua sem questões.
    assert client.get(f"/provas/{prova['id']}", headers=auth_headers(token)).json()["questoes"] == []
    corpos_log = b"\n".join(c.request.content for c in auth_service.routes[1].calls)
    assert f"questoes_geradas:prova:{prova['id']}:1".encode() in corpos_log


def test_descarta_questoes_malformadas_e_respeita_a_quantidade(client, garage_falso, ia):
    ia.mock(
        return_value=resposta_da_ia(
            [
                {"enunciado": "Sem alternativas", "alternativas": [], "resposta_correta": 0},
                {**QUESTAO_BOA, "resposta_correta": 7},  # gabarito fora da lista
                QUESTAO_BOA,
                {**QUESTAO_BOA, "enunciado": "Outra válida"},
            ]
        )
    )
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    resposta = client.post(
        f"/provas/{prova['id']}/gerar-questoes", json={"quantidade": 1}, headers=auth_headers(token)
    )

    assert resposta.status_code == 200
    assert [q["enunciado"] for q in resposta.json()["questoes"]] == [QUESTAO_BOA["enunciado"]]


def test_plano_free_nao_gera_nem_pela_api(client, garage_falso, ia):
    token = criar_token(role="professor")
    prova = prova_com_pdf(client, token)

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert resposta.status_code == 403
    assert not ia.called


def test_prova_de_outro_da_404(client, garage_falso, ia):
    prova = prova_com_pdf(client, criar_token(role="professor_pro"))
    intruso = criar_token(role="professor_pro")

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(intruso))

    assert resposta.status_code == 404
    assert not ia.called


def test_prova_sem_pdf_da_409(client, garage_falso, ia):
    token = criar_token(role="professor_pro")
    prova = criar_prova(client, token, criar_turma(client, token)["id"])

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert resposta.status_code == 409


def test_pdf_sem_texto_da_422_sem_chamar_a_ia(client, garage_falso, ia):
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token, conteudo=b"%PDF-1.4\n%%EOF\n")

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert resposta.status_code == 422
    assert not ia.called


def test_sem_chave_configurada_da_503(client, garage_falso, auth_service, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_api_key", "")
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert resposta.status_code == 503


@pytest.mark.parametrize(
    "resposta_do_provedor",
    [
        Response(429, json={"error": "rate limit"}),
        Response(500, text="erro interno"),
        Response(200, json={"choices": [{"message": {"content": "isso não é JSON"}}]}),
        Response(200, json={"choices": [{"message": {"content": "{\"questoes\": []}"}}]}),
    ],
)
def test_falha_do_provedor_vira_502(client, garage_falso, ia, resposta_do_provedor):
    ia.mock(return_value=resposta_do_provedor)
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert resposta.status_code == 502
