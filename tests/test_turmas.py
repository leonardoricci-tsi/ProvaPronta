from tests.conftest import auth_headers, criar_token

TURMA = {"nome": "1º A", "disciplina": "Biologia", "escola": "E.E. João Cruz", "ano_letivo": 2026}


def criar_turma(client, token, **campos):
    resposta = client.post("/turmas", json=TURMA | campos, headers=auth_headers(token))
    assert resposta.status_code == 201, resposta.text
    return resposta.json()


def test_crud_de_turma(client, auth_service):
    token = criar_token()

    turma = criar_turma(client, token)
    assert turma["total_alunos"] == 0

    editada = client.patch(f"/turmas/{turma['id']}", json={"nome": "1º B"}, headers=auth_headers(token))
    assert editada.status_code == 200
    assert editada.json()["nome"] == "1º B"
    assert editada.json()["disciplina"] == "Biologia"

    lista = client.get("/turmas", headers=auth_headers(token)).json()
    assert [t["nome"] for t in lista] == ["1º B"]

    assert client.delete(f"/turmas/{turma['id']}", headers=auth_headers(token)).status_code == 204
    assert client.get(f"/turmas/{turma['id']}", headers=auth_headers(token)).status_code == 404


def test_lista_so_as_turmas_do_proprio_professor(client, auth_service):
    token_a, token_b = criar_token(), criar_token()
    criar_turma(client, token_a, nome="Turma da A")
    criar_turma(client, token_b, nome="Turma do B")

    lista = client.get("/turmas", headers=auth_headers(token_a)).json()

    assert [t["nome"] for t in lista] == ["Turma da A"]


def test_turma_de_outro_professor_da_404_em_toda_acao(client, auth_service):
    """Trocar o ID na URL não abre nada: ler, editar, apagar e pôr aluno na
    turma de outra pessoa respondem 404 (sem nem confirmar que ela existe)."""
    token_dono, token_intruso = criar_token(), criar_token()
    turma = criar_turma(client, token_dono)
    url = f"/turmas/{turma['id']}"
    intruso = auth_headers(token_intruso)

    assert client.get(url, headers=intruso).status_code == 404
    assert client.patch(url, json={"nome": "hackeada"}, headers=intruso).status_code == 404
    assert client.delete(url, headers=intruso).status_code == 404
    aluno = {"nome": "Infiltrado", "numero_chamada": 99}
    assert client.post(f"{url}/alunos", json=aluno, headers=intruso).status_code == 404

    original = client.get(url, headers=auth_headers(token_dono)).json()
    assert original["nome"] == "1º A"
    assert original["alunos"] == []


def test_usuario_id_no_corpo_e_ignorado(client, auth_service):
    token_a = criar_token(usuario_id=801)
    token_b = criar_token(usuario_id=802)

    turma = criar_turma(client, token_a, usuario_id=802)

    assert client.get(f"/turmas/{turma['id']}", headers=auth_headers(token_a)).status_code == 200
    assert client.get(f"/turmas/{turma['id']}", headers=auth_headers(token_b)).status_code == 404


def test_alunos_da_turma(client, auth_service):
    token = criar_token()
    turma = criar_turma(client, token)
    url = f"/turmas/{turma['id']}/alunos"

    ana = client.post(url, json={"nome": "Ana", "numero_chamada": 1}, headers=auth_headers(token))
    client.post(url, json={"nome": "Bruno", "numero_chamada": 2}, headers=auth_headers(token))
    repetido = client.post(url, json={"nome": "Outra Ana", "numero_chamada": 1}, headers=auth_headers(token))

    assert ana.status_code == 201
    assert repetido.status_code == 409
    detalhe = client.get(f"/turmas/{turma['id']}", headers=auth_headers(token)).json()
    assert [a["nome"] for a in detalhe["alunos"]] == ["Ana", "Bruno"]

    remover = client.delete(f"{url}/{ana.json()['id']}", headers=auth_headers(token))
    assert remover.status_code == 204
    assert client.get("/turmas", headers=auth_headers(token)).json()[0]["total_alunos"] == 1


def test_nao_apaga_turma_que_tem_prova(client, auth_service):
    token = criar_token()
    turma = criar_turma(client, token)
    client.post("/provas", json={"turma_id": turma["id"], "titulo": "P1"}, headers=auth_headers(token))

    resposta = client.delete(f"/turmas/{turma['id']}", headers=auth_headers(token))

    assert resposta.status_code == 409


def test_plano_free_cria_so_uma_turma(client, auth_service):
    token = criar_token(role="professor")
    criar_turma(client, token)

    resposta = client.post("/turmas", json=TURMA | {"nome": "1º B"}, headers=auth_headers(token))

    assert resposta.status_code == 403
    assert "Free" in resposta.json()["detail"]
    rota_log = auth_service.routes[1]
    assert b"acesso_negado:limite_free:turmas" in rota_log.calls.last.request.content


def test_pro_cria_varias_turmas(client, auth_service):
    token = criar_token(role="professor_pro")
    for nome in ("1º A", "1º B", "2º A"):
        criar_turma(client, token, nome=nome)

    assert len(client.get("/turmas", headers=auth_headers(token)).json()) == 3


def test_eventos_de_turma_vao_pro_log(client, auth_service):
    token = criar_token(usuario_id=810)
    turma = criar_turma(client, token)
    client.post(f"/turmas/{turma['id']}/alunos", json={"nome": "Ana", "numero_chamada": 1}, headers=auth_headers(token))
    client.delete(f"/turmas/{turma['id']}/alunos/999", headers=auth_headers(token))

    acoes = [chamada.request.content for chamada in auth_service.routes[1].calls]

    assert any(f'"turma_criada:{turma["id"]}"'.encode() in corpo and b'"usuario_id":810' in corpo for corpo in acoes)
    assert any(f"aluno_adicionado:turma:{turma['id']}".encode() in corpo for corpo in acoes)


def test_turmas_exigem_login(client):
    assert client.get("/turmas").status_code == 401
    assert client.post("/turmas", json=TURMA).status_code == 401
