from tests.conftest import token_para


def test_registrar_evento_grava_no_stream(client, fake_redis):
    resposta = client.post("/logs", json={"usuario_id": 1, "acao": "login"})
    assert resposta.status_code == 201
    assert fake_redis.xlen("audit_log") == 1


def test_consultar_eventos_exige_admin(client):
    client.post("/logs", json={"usuario_id": 1, "acao": "login"})

    token_usuario_comum = token_para(1, "professor")
    resposta = client.get("/logs", headers={"Authorization": f"Bearer {token_usuario_comum}"})
    assert resposta.status_code == 403


def test_consultar_eventos_sem_token_e_401(client):
    resposta = client.get("/logs")
    assert resposta.status_code == 401


def test_consultar_eventos_como_admin_retorna_na_ordem_certa(client):
    client.post("/logs", json={"usuario_id": 1, "acao": "login"})
    client.post("/logs", json={"usuario_id": 1, "acao": "favoritar_filme"})
    client.post("/logs", json={"usuario_id": 2, "acao": "comentar", "ip": "127.0.0.1"})

    token_admin = token_para(99, "admin")
    resposta = client.get("/logs", headers={"Authorization": f"Bearer {token_admin}"})

    assert resposta.status_code == 200
    eventos = resposta.json()
    assert len(eventos) == 3
    # XREVRANGE: mais recente primeiro.
    assert [e["acao"] for e in eventos] == ["comentar", "favoritar_filme", "login"]
    assert eventos[0]["ip"] == "127.0.0.1"
    assert eventos[1]["ip"] is None


def test_consultar_eventos_respeita_limit(client):
    for i in range(5):
        client.post("/logs", json={"usuario_id": 1, "acao": f"acao_{i}"})

    token_admin = token_para(99, "admin")
    resposta = client.get("/logs?limit=2", headers={"Authorization": f"Bearer {token_admin}"})

    assert resposta.status_code == 200
    assert len(resposta.json()) == 2
