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
    # Padrão é o GPT OSS (Groq): raciocínio curto pra responder rápido.
    assert pedido["reasoning_effort"] == "low"
    mensagem = pedido["messages"][1]["content"]
    assert "Crie 3 questões" in mensagem and "mitocôndria" in mensagem
    # A disciplina da turma é contexto, não restrição: material de outra
    # disciplina ainda gera questões sobre o material.
    assert "turma de Biologia" in mensagem and "sobre o conteúdo do material" in mensagem
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
def test_falha_do_provedor_vira_503(client, garage_falso, ia, resposta_do_provedor):
    ia.mock(return_value=resposta_do_provedor)
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    # 503, não 502: o Cloudflare troca 502 da origem pela página dele.
    assert resposta.status_code == 503
    assert "IA" in resposta.json()["detail"]


def test_aceita_json_embrulhado_em_bloco_de_codigo(client, garage_falso, ia):
    embrulhado = "Aqui estão as questões:\n```json\n" + json.dumps({"questoes": [QUESTAO_BOA]}) + "\n```"
    ia.mock(return_value=Response(200, json={"choices": [{"message": {"content": embrulhado}}]}))
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert resposta.status_code == 200
    assert resposta.json()["questoes"] == [QUESTAO_BOA]


def test_reasoning_effort_so_vai_para_modelos_gpt_oss(client, garage_falso, ia, monkeypatch):
    monkeypatch.setattr(get_settings(), "llm_model", "claude-qualquer")
    ia.mock(return_value=resposta_da_ia([QUESTAO_BOA]))
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert "reasoning_effort" not in json.loads(ia.calls.last.request.content)


@pytest.mark.parametrize(
    "variacao, esperado",
    [
        # Resposta como letra, com e sem pontuação.
        ({**QUESTAO_BOA, "resposta_correta": "B"}, 1),
        ({**QUESTAO_BOA, "resposta_correta": "b)"}, 1),
        ({**QUESTAO_BOA, "resposta_correta": "B) Mitocôndria"}, 1),
        # Resposta como o texto da alternativa.
        ({**QUESTAO_BOA, "resposta_correta": "mitocôndria"}, 1),
        # Contando a partir de 1 só quando não dá pra ser 0-based (4 de 4).
        ({**QUESTAO_BOA, "resposta_correta": 4}, 3),
        ({**QUESTAO_BOA, "resposta_correta": "2"}, 2),
        # Alternativas com prefixo de letra e como objeto {"A": ...}.
        ({**QUESTAO_BOA, "alternativas": ["A) Ribossomo", "B) Mitocôndria", "C) Lisossomo", "D) Golgi"]}, 1),
        (
            {**QUESTAO_BOA, "alternativas": {"A": "Ribossomo", "B": "Mitocôndria", "C": "Lisossomo", "D": "Golgi"}},
            1,
        ),
        # Chaves com outros nomes.
        (
            {
                "pergunta": QUESTAO_BOA["enunciado"],
                "opcoes": QUESTAO_BOA["alternativas"],
                "gabarito": "B",
                "tema": "Organelas",
            },
            1,
        ),
    ],
)
def test_aceita_variacoes_comuns_do_modelo(variacao, esperado):
    from app.services.gerador_questoes import _questoes_validas

    [questao] = _questoes_validas({"questoes": [variacao]}, 5)

    assert questao.resposta_correta == esperado
    assert questao.alternativas == QUESTAO_BOA["alternativas"]
    assert questao.enunciado == QUESTAO_BOA["enunciado"]


def test_aceita_lista_solta_ou_com_outro_nome():
    from app.services.gerador_questoes import _questoes_validas

    assert len(_questoes_validas([QUESTAO_BOA], 5)) == 1
    assert len(_questoes_validas({"questions": [QUESTAO_BOA]}, 5)) == 1


def test_nao_corta_alternativa_que_so_parece_letra():
    from app.services.gerador_questoes import _questoes_validas

    alternativas = ["Vírus", "Fungo", "Protozoário", "E. coli é uma bactéria"]
    [questao] = _questoes_validas(
        {"questoes": [{"enunciado": "Qual é bactéria?", "alternativas": alternativas, "resposta_correta": 3}]}, 5
    )

    assert questao.alternativas == alternativas


def test_resposta_que_nao_bate_com_nada_descarta_a_questao():
    from app.services.gerador_questoes import _questoes_validas

    assert _questoes_validas({"questoes": [{**QUESTAO_BOA, "resposta_correta": "Núcleo"}]}, 5) == []


def test_lista_vazia_com_motivo_mostra_o_motivo(client, garage_falso, ia):
    conteudo = json.dumps({"questoes": [], "motivo": "O texto do material está ilegível."})
    ia.mock(return_value=Response(200, json={"choices": [{"message": {"content": conteudo}}]}))
    token = criar_token(role="professor_pro")
    prova = prova_com_pdf(client, token)

    resposta = client.post(f"/provas/{prova['id']}/gerar-questoes", headers=auth_headers(token))

    assert resposta.status_code == 422
    assert resposta.json()["detail"] == "A IA não conseguiu gerar questões: O texto do material está ilegível."
