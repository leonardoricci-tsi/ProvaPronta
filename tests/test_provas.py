from datetime import timedelta

from app.models import Prova
from tests.conftest import auth_headers, criar_token

QUESTOES = [
    {
        "enunciado": "Qual organela faz a respiração celular?",
        "alternativas": ["Ribossomo", "Mitocôndria", "Lisossomo", "Golgi"],
        "resposta_correta": 1,
        "assunto": "Citologia",
    },
    {
        "enunciado": "A membrana plasmática é formada por:",
        "alternativas": ["Celulose", "Fosfolipídios", "Amido"],
        "resposta_correta": 1,
    },
]


def criar_turma(client, token):
    corpo = {"nome": "1º A", "disciplina": "Biologia", "ano_letivo": 2026}
    resposta = client.post("/turmas", json=corpo, headers=auth_headers(token))
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def criar_prova(client, token, turma_id, **campos):
    corpo = {"turma_id": turma_id, "titulo": "Avaliação bimestral", "questoes": QUESTOES} | campos
    resposta = client.post("/provas", json=corpo, headers=auth_headers(token))
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_crud_de_prova(client, auth_service):
    token = criar_token()
    turma = criar_turma(client, token)

    prova = criar_prova(client, token, turma["id"], data_aplicacao="2026-11-20")
    assert prova["status"] == "rascunho"
    assert prova["turma"]["nome"] == "1º A"
    assert [q["ordem"] for q in prova["questoes"]] == [1, 2]
    assert prova["questoes"][0]["resposta_correta"] == 1

    lista = client.get("/provas", headers=auth_headers(token)).json()
    assert [(p["titulo"], p["total_questoes"]) for p in lista] == [("Avaliação bimestral", 2)]

    editada = client.patch(
        f"/provas/{prova['id']}",
        json={"titulo": "P1 — Citologia", "status": "pronta", "questoes": QUESTOES[:1]},
        headers=auth_headers(token),
    ).json()
    assert (editada["titulo"], editada["status"], editada["total_questoes"]) == ("P1 — Citologia", "pronta", 1)
    assert editada["data_aplicacao"] == "2026-11-20"

    assert client.delete(f"/provas/{prova['id']}", headers=auth_headers(token)).status_code == 204
    assert client.get(f"/provas/{prova['id']}", headers=auth_headers(token)).status_code == 404


def test_prova_de_outro_professor_da_404_em_toda_acao(client, auth_service):
    token_dono, token_intruso = criar_token(), criar_token()
    prova = criar_prova(client, token_dono, criar_turma(client, token_dono)["id"])
    url = f"/provas/{prova['id']}"
    intruso = auth_headers(token_intruso)

    assert client.get(url, headers=intruso).status_code == 404
    assert client.patch(url, json={"titulo": "hackeada"}, headers=intruso).status_code == 404
    assert client.delete(url, headers=intruso).status_code == 404
    assert client.post(f"{url}/versao-b", headers=intruso).status_code == 404
    assert client.get("/provas", headers=intruso).json() == []
    assert client.get(url, headers=auth_headers(token_dono)).json()["titulo"] == "Avaliação bimestral"


def test_nao_cria_nem_move_prova_pra_turma_de_outro(client, auth_service):
    token_a, token_b = criar_token(), criar_token()
    turma_de_b = criar_turma(client, token_b)
    prova_de_a = criar_prova(client, token_a, criar_turma(client, token_a)["id"])

    criar = client.post(
        "/provas", json={"turma_id": turma_de_b["id"], "titulo": "x"}, headers=auth_headers(token_a)
    )
    mover = client.patch(
        f"/provas/{prova_de_a['id']}", json={"turma_id": turma_de_b["id"]}, headers=auth_headers(token_a)
    )

    assert criar.status_code == 404
    assert mover.status_code == 404
    assert client.get("/provas", params={"turma_id": turma_de_b["id"]}, headers=auth_headers(token_a)).json() == []


def test_gabarito_tem_que_apontar_pra_uma_alternativa(client, auth_service):
    token = criar_token()
    turma = criar_turma(client, token)
    questao_invalida = QUESTOES[1] | {"resposta_correta": 3}

    resposta = client.post(
        "/provas",
        json={"turma_id": turma["id"], "titulo": "x", "questoes": [questao_invalida]},
        headers=auth_headers(token),
    )

    assert resposta.status_code == 422


def test_versao_b_embaralha_e_mantem_o_gabarito(client, auth_service):
    token = criar_token(role="professor_pro")
    original = criar_prova(client, token, criar_turma(client, token)["id"])

    resposta = client.post(f"/provas/{original['id']}/versao-b", headers=auth_headers(token))

    assert resposta.status_code == 201
    versao_b = resposta.json()
    assert versao_b["titulo"] == "Avaliação bimestral (versão B)"
    assert versao_b["id"] != original["id"]
    certas_original = {q["enunciado"]: q["alternativas"][q["resposta_correta"]] for q in original["questoes"]}
    certas_b = {q["enunciado"]: q["alternativas"][q["resposta_correta"]] for q in versao_b["questoes"]}
    assert certas_b == certas_original


def test_plano_free_nao_gera_versao_b_nem_pela_api(client, auth_service):
    """O botão nem aparece pro Free, mas o que vale é o backend: chamada
    direta na API também leva 403."""
    token = criar_token(role="professor")
    prova = criar_prova(client, token, criar_turma(client, token)["id"])

    resposta = client.post(f"/provas/{prova['id']}/versao-b", headers=auth_headers(token))

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Ação exige papel 'professor_pro' ou superior"
    assert len(client.get("/provas", headers=auth_headers(token)).json()) == 1
    rota_log = auth_service.routes[1]
    assert b"acesso_negado:professor_pro" in rota_log.calls.last.request.content


def test_plano_free_cria_2_provas_por_mes(client, auth_service, db_session):
    token = criar_token(role="professor")
    turma = criar_turma(client, token)
    criar_prova(client, token, turma["id"])
    segunda = criar_prova(client, token, turma["id"])

    terceira = client.post("/provas", json={"turma_id": turma["id"], "titulo": "P3"}, headers=auth_headers(token))
    assert terceira.status_code == 403

    # Prova do mês passado não conta no limite deste mês.
    db_session.get(Prova, segunda["id"]).criado_em -= timedelta(days=40)
    db_session.commit()
    assert client.post("/provas", json={"turma_id": turma["id"], "titulo": "P3"}, headers=auth_headers(token)).status_code == 201


def test_eventos_de_prova_vao_pro_log(client, auth_service):
    token = criar_token(usuario_id=820)
    prova = criar_prova(client, token, criar_turma(client, token)["id"])
    client.patch(f"/provas/{prova['id']}", json={"status": "pronta"}, headers=auth_headers(token))
    versao_b = client.post(f"/provas/{prova['id']}/versao-b", headers=auth_headers(token)).json()
    client.delete(f"/provas/{prova['id']}", headers=auth_headers(token))

    corpos = b"\n".join(chamada.request.content for chamada in auth_service.routes[1].calls)

    for acao in (
        f"prova_criada:{prova['id']}",
        f"prova_editada:{prova['id']}",
        f"prova_versao_b:{prova['id']}:nova:{versao_b['id']}",
        f"prova_removida:{prova['id']}",
    ):
        assert acao.encode() in corpos
    assert b'"usuario_id":820' in corpos


def test_provas_exigem_login(client):
    assert client.get("/provas").status_code == 401
    assert client.get("/provas/1").status_code == 401
