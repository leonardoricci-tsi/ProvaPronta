"""Plano Escola (papel `coordenador`): aprovar prova e relatório da
coordenação. Professor e Pro levam 403 mesmo chamando a API direto."""

import pytest

from tests.conftest import auth_headers, criar_token
from tests.test_provas import QUESTOES, criar_prova, criar_turma


def eventos(auth_service) -> bytes:
    return b"\n".join(chamada.request.content for chamada in auth_service.routes[1].calls)


@pytest.mark.parametrize("papel", ["professor", "professor_pro"])
def test_so_coordenador_aprova_prova_nem_pela_api(client, auth_service, papel):
    token = criar_token(role=papel)
    # O Free cria a 1ª turma e a 1ª prova normalmente (dentro do limite).
    turma = criar_turma(client, token)
    prova = criar_prova(client, token, turma["id"], status="pronta")

    resposta = client.post(f"/provas/{prova['id']}/aprovar", headers=auth_headers(token))

    assert resposta.status_code == 403
    assert resposta.json()["detail"] == "Ação exige papel 'coordenador' ou superior"
    assert client.get(f"/provas/{prova['id']}", headers=auth_headers(token)).json()["status"] == "pronta"
    assert b"acesso_negado:coordenador" in eventos(auth_service)


def test_ninguem_se_autoaprova_mandando_status_no_corpo(client, auth_service):
    token = criar_token(role="professor_pro")
    turma = criar_turma(client, token)

    criacao = client.post(
        "/provas",
        json={"turma_id": turma["id"], "titulo": "P1", "status": "aprovada"},
        headers=auth_headers(token),
    )
    assert criacao.status_code == 422

    prova = criar_prova(client, token, turma["id"], status="pronta")
    edicao = client.patch(
        f"/provas/{prova['id']}", json={"status": "aprovada"}, headers=auth_headers(token)
    )
    assert edicao.status_code == 422


def test_coordenador_aprova_prova_pronta(client, auth_service):
    token = criar_token(role="coordenador")
    turma = criar_turma(client, token)
    prova = criar_prova(client, token, turma["id"], status="pronta")

    resposta = client.post(f"/provas/{prova['id']}/aprovar", headers=auth_headers(token))

    assert resposta.status_code == 200
    assert resposta.json()["status"] == "aprovada"
    assert f"prova_aprovada:{prova['id']}".encode() in eventos(auth_service)
    # Aprovar de novo não faz sentido.
    de_novo = client.post(f"/provas/{prova['id']}/aprovar", headers=auth_headers(token))
    assert (de_novo.status_code, de_novo.json()["detail"]) == (409, "A prova já está aprovada")


def test_rascunho_nao_pode_ser_aprovado(client, auth_service):
    token = criar_token(role="coordenador")
    turma = criar_turma(client, token)
    prova = criar_prova(client, token, turma["id"])

    resposta = client.post(f"/provas/{prova['id']}/aprovar", headers=auth_headers(token))

    assert (resposta.status_code, resposta.json()["detail"]) == (409, "Só prova pronta pode ser aprovada")


def test_admin_tambem_aprova(client, auth_service):
    token = criar_token(role="admin")
    turma = criar_turma(client, token)
    prova = criar_prova(client, token, turma["id"], status="pronta")

    assert client.post(f"/provas/{prova['id']}/aprovar", headers=auth_headers(token)).status_code == 200


def test_coordenador_nao_aprova_prova_de_outro(client, auth_service):
    dono = criar_token(role="professor_pro")
    turma = criar_turma(client, dono)
    prova = criar_prova(client, dono, turma["id"], status="pronta")

    coordenador = criar_token(role="coordenador")
    resposta = client.post(f"/provas/{prova['id']}/aprovar", headers=auth_headers(coordenador))

    assert resposta.status_code == 404


def test_editar_prova_aprovada_tira_a_aprovacao(client, auth_service):
    token = criar_token(role="coordenador")
    turma = criar_turma(client, token)
    prova = criar_prova(client, token, turma["id"], status="pronta")
    client.post(f"/provas/{prova['id']}/aprovar", headers=auth_headers(token))

    editada = client.patch(
        f"/provas/{prova['id']}", json={"questoes": QUESTOES[:1]}, headers=auth_headers(token)
    ).json()

    assert editada["status"] == "pronta"


@pytest.mark.parametrize("papel", ["professor", "professor_pro"])
def test_relatorio_so_para_coordenador_nem_pela_api(client, auth_service, papel):
    resposta = client.get("/coordenacao/relatorio", headers=auth_headers(criar_token(role=papel)))

    assert resposta.status_code == 403
    assert b"acesso_negado:coordenador" in eventos(auth_service)


def test_relatorio_conta_turmas_provas_e_assuntos_so_do_proprio_usuario(client, auth_service):
    token = criar_token(role="coordenador")
    turma = criar_turma(client, token)
    client.post(
        f"/turmas/{turma['id']}/alunos",
        json={"nome": "Ana", "numero_chamada": 1},
        headers=auth_headers(token),
    )
    pronta = criar_prova(client, token, turma["id"], status="pronta")
    client.post(f"/provas/{pronta['id']}/aprovar", headers=auth_headers(token))
    criar_prova(client, token, turma["id"])  # rascunho

    # Dados de outra pessoa não entram no relatório.
    outro = criar_token(role="coordenador")
    criar_prova(client, outro, criar_turma(client, outro)["id"])

    resposta = client.get("/coordenacao/relatorio", headers=auth_headers(token))

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["totais"] == {
        "turmas": 1,
        "alunos": 1,
        "provas": 2,
        "provas_aprovadas": 1,
        "questoes": 4,
    }
    linha = corpo["turmas"][0]
    assert (linha["total_alunos"], linha["total_questoes"]) == (1, 4)
    assert linha["provas"] == {"rascunho": 1, "pronta": 0, "aprovada": 1}
    # QUESTOES tem uma de "Citologia" e uma sem assunto, em cada prova.
    assert corpo["assuntos"] == [
        {"assunto": "Citologia", "questoes": 2, "provas": 2},
        {"assunto": "Sem assunto", "questoes": 2, "provas": 2},
    ]
    assert b"relatorio_coordenacao_consultado" in eventos(auth_service)
