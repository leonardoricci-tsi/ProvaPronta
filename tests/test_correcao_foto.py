"""Correção por foto (parte 1): leitura da folha fotografada.

As "fotos" são montadas aqui com a MESMA geometria da folha impressa
(`folha_resposta`): marcas, QR assinado e bolinhas, depois colocadas em
perspectiva sobre uma mesa, com sombra, girada e comprimida em JPEG — o que
um celular faz com a folha de verdade."""

import cv2
import numpy as np
import pytest

from app.services import folha_resposta as fr
from app.services import leitura_folha as lf
from tests.conftest import auth_headers, criar_token
from tests.test_folha_resposta import turma_com_alunos
from tests.test_provas import criar_prova, criar_turma

K = 2.0  # pixels por ponto da folha "impressa"


def _px(x: float, y: float) -> tuple[int, int]:
    return round(x * K), round((fr.ALTURA - y) * K)


def folha_impressa(prova_id: int, aluno_id: int, alternativas: list[int], marcas: dict[int, list[int]], qr=None):
    """Imagem (BGR) da folha com as bolinhas de `marcas` (questão -> alternativas) pintadas."""
    img = np.full((round(fr.ALTURA * K), round(fr.LARGURA * K), 3), 255, np.uint8)
    for cx, cy in fr.centros_das_marcas():
        x0, y0 = _px(cx - fr.MARCA_LADO / 2, cy + fr.MARCA_LADO / 2)
        x1, y1 = _px(cx + fr.MARCA_LADO / 2, cy - fr.MARCA_LADO / 2)
        cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 0), -1)

    codigo = cv2.QRCodeEncoder.create().encode(qr or fr.conteudo_qr(prova_id, aluno_id))
    lado = round(fr.QR_LADO * K)
    codigo = cv2.resize(codigo, (lado, lado), interpolation=cv2.INTER_NEAREST)
    x0, y0 = _px(fr.QR_X, fr.QR_Y + fr.QR_LADO)
    img[y0 : y0 + lado, x0 : x0 + lado] = cv2.cvtColor(codigo, cv2.COLOR_GRAY2BGR)

    cv2.putText(img, "ProvaPronta - Folha de respostas", _px(fr.MARCA_MARGEM + fr.MARCA_LADO + 12, fr.ALTURA - 45), 0, 0.8, (0, 0, 0), 2)
    raio = round(fr.BOLINHA_RAIO * K)
    for q, total in enumerate(alternativas):
        for a in range(total):
            centro = _px(*fr.centro_da_bolinha(q, a))
            cv2.circle(img, centro, raio, (0, 0, 0), 1, cv2.LINE_AA)
            cv2.putText(img, "ABCDE"[a], (centro[0] - 4, centro[1] + 4), 0, 0.35, (0, 0, 0), 1, cv2.LINE_AA)
    for q, alternativas_marcadas in marcas.items():
        for a in alternativas_marcadas:
            # Caneta azul nas pares, preta nas ímpares; nunca exatamente no centro.
            cor = (150, 50, 20) if q % 2 == 0 else (35, 35, 35)
            x, y = _px(*fr.centro_da_bolinha(q, a))
            cv2.circle(img, (x + 1, y - 1), round(raio * 0.85), cor, -1)
    return img


def fotografar(img, giro=0, perspectiva=0, sombra=False) -> bytes:
    h, w = img.shape[:2]
    alto, largo, margem = 2000, 1500, 100
    mesa = np.full((alto, largo, 3), (60, 85, 110), np.uint8)
    destino = np.float32(
        [
            [margem + perspectiva, margem],
            [largo - margem, margem + perspectiva / 2],
            [largo - margem - perspectiva / 3, alto - margem],
            [margem, alto - margem - perspectiva],
        ]
    )
    matriz = cv2.getPerspectiveTransform(np.float32([[0, 0], [w, 0], [w, h], [0, h]]), destino)
    foto = cv2.warpPerspective(img, matriz, (largo, alto), dst=mesa, borderMode=cv2.BORDER_TRANSPARENT)
    if sombra:
        luz = np.linspace(1.0, 0.45, largo)[None, :, None] * np.linspace(1.0, 0.8, alto)[:, None, None]
        foto = (foto * luz).astype(np.uint8)
    foto = cv2.GaussianBlur(np.rot90(foto, giro).copy(), (3, 3), 0)
    return cv2.imencode(".jpg", foto, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


ALTERNATIVAS = [4] * 20 + [5] * 10
GABARITO = {q: [(q * 7) % ALTERNATIVAS[q]] for q in range(30)}


@pytest.mark.parametrize(
    "cenario",
    [
        {},
        {"perspectiva": 150},
        {"perspectiva": 100, "sombra": True},
        {"giro": 1, "perspectiva": 80, "sombra": True},  # celular deitado
        {"giro": 2, "perspectiva": 60},  # de cabeça pra baixo
        {"giro": 3},
    ],
)
def test_le_qr_e_todas_as_respostas_mesmo_torta_e_com_sombra(cenario):
    foto = fotografar(folha_impressa(3, 12, ALTERNATIVAS, GABARITO), **cenario)

    leitura = lf.ler_folha(foto, ALTERNATIVAS)

    assert (leitura.prova_id, leitura.aluno_id) == (3, 12)
    assert [q.situacao for q in leitura.questoes] == ["ok"] * 30
    assert [q.marcada for q in leitura.questoes] == [GABARITO[q][0] for q in range(30)]


def test_em_branco_varias_e_marca_fraca_vao_pra_conferir():
    marcas = {0: [1], 1: [], 2: [0, 2]}
    img = folha_impressa(3, 12, [4, 4, 4, 4], marcas)
    # Questão 4: só um risquinho na B, sem pintar.
    x, y = _px(*fr.centro_da_bolinha(3, 1))
    cv2.line(img, (x - 5, y), (x + 5, y), (30, 30, 30), 5)

    leitura = lf.ler_folha(fotografar(img, perspectiva=60), [4, 4, 4, 4])

    assert [(q.situacao, q.marcada) for q in leitura.questoes] == [
        ("ok", 1),
        ("em_branco", None),
        ("varias", None),
        ("duvida", None),
    ]


def test_qr_com_assinatura_falsa_nao_e_aceito():
    """Trocar o aluno do QR sem saber o segredo do servidor não passa."""
    assinatura_de_outro = fr.conteudo_qr(3, 12).split(":")[3]
    img = folha_impressa(3, 13, [4], {}, qr=f"PP2:3:13:{assinatura_de_outro}")
    with pytest.raises(lf.QrIlegivel):
        lf.ler_folha(fotografar(img), [4])


def test_foto_sem_folha_ou_que_nao_e_imagem():
    mesa = np.full((800, 600, 3), (60, 85, 110), np.uint8)
    cv2.rectangle(mesa, (100, 100), (200, 200), (0, 0, 0), -1)
    with pytest.raises(lf.FolhaNaoEncontrada):
        lf.ler_folha(cv2.imencode(".jpg", mesa)[1].tobytes(), [4])
    with pytest.raises(lf.ImagemInvalida):
        lf.ler_folha(b"%PDF-1.4 nao sou foto", [4])
    with pytest.raises(lf.ImagemGrandeDemais):
        lf.ler_folha(b"0" * (lf.TAMANHO_MAXIMO_BYTES + 1), [4])


# --- API ---------------------------------------------------------------------


def _enviar(client, token, prova_id, foto: bytes, nome="folha.jpg"):
    return client.post(
        f"/provas/{prova_id}/correcao/leitura",
        files={"foto": (nome, foto, "image/jpeg")},
        headers=auth_headers(token),
    )


def test_api_devolve_respostas_acertos_e_nota_recomendada(client, auth_service):
    token = criar_token()
    turma = turma_com_alunos(client, token)
    prova = criar_prova(client, token, turma["id"])  # 2 questões, gabarito B e B
    bruno = client.get(f"/turmas/{turma['id']}", headers=auth_headers(token)).json()["alunos"][1]
    # Acerta a 1ª (B), erra a 2ª (marcou C).
    foto = fotografar(folha_impressa(prova["id"], bruno["id"], [4, 3], {0: [1], 1: [2]}), perspectiva=80)

    resposta = _enviar(client, token, prova["id"], foto)

    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["aluno"] == {"id": bruno["id"], "nome": "Bruno Lima", "numero_chamada": 2}
    assert [(r["numero"], r["marcada"], r["correta"], r["acertou"]) for r in corpo["respostas"]] == [
        (1, 1, 1, True),
        (2, 2, 1, False),
    ]
    assert (corpo["acertos"], corpo["total"], corpo["nota_recomendada"], corpo["conferir"]) == (1, 2, 5.0, [])
    corpos = b"\n".join(c.request.content for c in auth_service.routes[1].calls)
    assert f"folha_lida:prova:{prova['id']}:aluno:{bruno['id']}:1/2".encode() in corpos


def test_api_recusa_folha_de_outra_prova_e_prova_de_outro(client, auth_service):
    token = criar_token()
    turma = turma_com_alunos(client, token)
    prova = criar_prova(client, token, turma["id"])
    outra = criar_prova(client, token, turma["id"])
    aluno_id = client.get(f"/turmas/{turma['id']}", headers=auth_headers(token)).json()["alunos"][0]["id"]
    foto_da_outra = fotografar(folha_impressa(outra["id"], aluno_id, [4, 3], {0: [1]}))

    resposta = _enviar(client, token, prova["id"], foto_da_outra)
    assert resposta.status_code == 422
    assert f"prova {outra['id']}" in resposta.json()["detail"]

    # Prova de outro professor: 404, como se não existisse.
    assert _enviar(client, criar_token(), outra["id"], foto_da_outra).status_code == 404


def test_api_arquivo_que_nao_e_foto_e_prova_sem_questoes(client, auth_service):
    token = criar_token()
    prova = criar_prova(client, token, criar_turma(client, token)["id"])
    assert _enviar(client, token, prova["id"], b"%PDF-1.4", nome="x.pdf").status_code == 415

    vazia = criar_prova(client, token, criar_turma(client, token)["id"], questoes=[])
    assert _enviar(client, token, vazia["id"], b"qualquer").status_code == 409
