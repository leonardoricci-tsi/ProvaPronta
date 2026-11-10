"""Correção por foto: lê a folha de respostas fotografada pelo celular.

Passos, todos com OpenCV (visão computacional clássica, sem IA — por isso a
correção cabe no plano Free):

1. acha as 4 marcas pretas dos cantos;
2. "endireita" a foto (transformação de perspectiva) levando as marcas de
   volta às posições que elas têm no PDF — a partir daí cada ponto da folha
   está onde `folha_resposta` desenhou;
3. lê o QR code (prova + aluno, assinado). Se ele não estiver no canto
   superior direito, a foto está girada: tenta as 4 rotações;
4. mede quanto de cada bolinha está pintado e decide a resposta da questão.

A geometria vem toda de `folha_resposta`: o mesmo módulo que desenha é o que
diz onde ler.
"""

import io
from dataclasses import dataclass

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

from app.services import folha_resposta as fr

TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024
PIXELS_MAXIMOS = 40_000_000  # foto de celular de 12–48 MP, antes de reduzir
# A foto é reduzida pra este lado maior antes de procurar as marcas: sobra
# resolução (a folha inteira vira ~1600 px) e o processamento fica rápido.
LADO_MAXIMO = 2000

# A folha endireitada é desenhada nesta escala (pixels por ponto do PDF).
ESCALA = 2.0
LARGURA_PX = round(fr.LARGURA * ESCALA)
ALTURA_PX = round(fr.ALTURA * ESCALA)

# Só o miolo da bolinha é medido (o contorno impresso fica de fora).
RAIO_AMOSTRA = 0.7 * fr.BOLINHA_RAIO
# Fração do miolo pintada: acima de MARCADA conta como resposta; entre
# DUVIDA e MARCADA é "pintou pouco" e vai pro professor conferir. A letra
# impressa dentro da bolinha vazia dá uns 10–20%.
LIMIAR_MARCADA = 0.45
LIMIAR_DUVIDA = 0.28


class ImagemInvalida(Exception):
    """O arquivo não é uma imagem (ou é grande demais em pixels)."""


class ImagemGrandeDemais(Exception):
    """Arquivo passou de TAMANHO_MAXIMO_BYTES."""


class FolhaNaoEncontrada(Exception):
    """Não achou as 4 marcas dos cantos na foto."""


class QrIlegivel(Exception):
    """Achou a folha, mas não conseguiu ler um QR válido nela."""


@dataclass
class LeituraQuestao:
    # Índice da alternativa marcada (0 = A), ou None se em branco/ambígua.
    marcada: int | None
    # "ok", "em_branco", "varias" (mais de uma pintada) ou "duvida" (pintou pouco).
    situacao: str
    # Fração pintada de cada alternativa, 0–1 (pra tela de revisão).
    preenchimento: list[float]


@dataclass
class LeituraFolha:
    prova_id: int
    aluno_id: int
    questoes: list[LeituraQuestao]


def _abrir(conteudo: bytes) -> np.ndarray:
    """Bytes da foto -> imagem em tons de cinza, já na orientação do EXIF
    (celular costuma gravar a foto deitada e a rotação só no EXIF)."""
    if len(conteudo) > TAMANHO_MAXIMO_BYTES:
        raise ImagemGrandeDemais
    try:
        with Image.open(io.BytesIO(conteudo)) as imagem:
            if imagem.width * imagem.height > PIXELS_MAXIMOS:
                raise ImagemInvalida
            imagem = ImageOps.exif_transpose(imagem)
            imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
            cinza = np.asarray(imagem.convert("L"))
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as erro:
        raise ImagemInvalida from erro
    return cinza


def _achar_marcas(cinza: np.ndarray) -> np.ndarray:
    """Centros das 4 marcas, em ordem horária a partir do canto superior
    esquerdo da FOTO (sup.esq, sup.dir, inf.dir, inf.esq)."""
    suave = cv2.GaussianBlur(cinza, (5, 5), 0)
    # Limiar adaptativo: aguenta sombra e luz desigual na foto.
    lado_bloco = max(31, (min(cinza.shape) // 20) | 1)
    binaria = cv2.adaptiveThreshold(suave, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, lado_bloco, 15)
    contornos, _ = cv2.findContours(binaria, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    area_minima = (min(cinza.shape) * 0.012) ** 2
    candidatos: list[tuple[float, float, float]] = []  # (x, y, área)
    for contorno in contornos:
        area = cv2.contourArea(contorno)
        if area < area_minima:
            continue
        (cx, cy), (w, h), _ = cv2.minAreaRect(contorno)
        if w == 0 or h == 0 or not 0.6 < w / h < 1.6:
            continue
        # Quadrado cheio ocupa ~todo o retângulo mínimo; a bolinha (círculo)
        # ocupa ~78% e fica de fora.
        if area / (w * h) < 0.85:
            continue
        aproximado = cv2.approxPolyDP(contorno, 0.06 * cv2.arcLength(contorno, True), True)
        if len(aproximado) != 4:
            continue
        # Tem que ser preto por dentro: o padrão de canto do QR (quadrado
        # com anel branco) e letras vazadas ficam de fora.
        mascara = np.zeros(cinza.shape, np.uint8)
        cv2.drawContours(mascara, [contorno], -1, 255, -1)
        if cv2.mean(binaria, mask=mascara)[0] / 255 < 0.85:
            continue
        candidatos.append((cx, cy, area))

    if len(candidatos) < 4:
        raise FolhaNaoEncontrada

    # As marcas são os maiores quadrados pretos da folha; ficam os parecidos
    # com o maior e, entre eles, os mais extremos em cada canto.
    maior = max(a for _, _, a in candidatos)
    pontos = np.array([(x, y) for x, y, a in candidatos if a >= maior * 0.3], dtype=np.float32)
    if len(pontos) < 4:
        raise FolhaNaoEncontrada
    soma, diferenca = pontos.sum(axis=1), pontos[:, 0] - pontos[:, 1]
    cantos = np.array(
        [
            pontos[np.argmin(soma)],  # sup. esq.
            pontos[np.argmax(diferenca)],  # sup. dir.
            pontos[np.argmax(soma)],  # inf. dir.
            pontos[np.argmin(diferenca)],  # inf. esq.
        ],
        dtype=np.float32,
    )
    if len({tuple(c) for c in cantos.tolist()}) < 4 or cv2.contourArea(cantos) < cinza.size * 0.1:
        # Cantos repetidos ou "folha" minúscula: não é a nossa folha inteira.
        raise FolhaNaoEncontrada
    return cantos


def _para_pixel(x: float, y: float) -> tuple[float, float]:
    """Ponto do PDF (origem embaixo à esquerda) -> pixel da folha endireitada."""
    return x * ESCALA, (fr.ALTURA - y) * ESCALA


def _endireitar(cinza: np.ndarray, cantos_foto: np.ndarray) -> np.ndarray:
    destino = np.array([_para_pixel(x, y) for x, y in fr.centros_das_marcas()], dtype=np.float32)
    matriz = cv2.getPerspectiveTransform(cantos_foto, destino)
    return cv2.warpPerspective(cinza, matriz, (LARGURA_PX, ALTURA_PX), flags=cv2.INTER_LINEAR, borderValue=255)


def _ler_qr(folha: np.ndarray) -> tuple[int, int] | None:
    margem = 6 * ESCALA * 2.83  # ~6 mm em volta do QR
    x0, y1 = _para_pixel(fr.QR_X, fr.QR_Y)
    x1, y0 = _para_pixel(fr.QR_X + fr.QR_LADO, fr.QR_Y + fr.QR_LADO)
    recorte = folha[
        max(0, int(y0 - margem)) : int(y1 + margem),
        max(0, int(x0 - margem)) : int(x1 + margem),
    ]
    detector = cv2.QRCodeDetector()
    for imagem in (recorte, cv2.resize(recorte, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)):
        try:
            texto, _, _ = detector.detectAndDecode(imagem)
        except cv2.error:
            continue
        if texto:
            return fr.ler_conteudo_qr(texto)
    return None


def _normalizar_luz(folha: np.ndarray) -> np.ndarray:
    """Divide pela "luz de fundo" (a folha sem as marcas pequenas), tirando
    sombra e degradê: papel vira ~255 em todo lugar e a tinta fica escura."""
    lado = int(fr.BOLINHA_RAIO * ESCALA * 4) | 1
    fundo = cv2.morphologyEx(folha, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (lado, lado)))
    return cv2.divide(folha, np.maximum(fundo, 1), scale=255)


def _preenchimento(tinta: np.ndarray, x: float, y: float) -> float:
    cx, cy = _para_pixel(x, y)
    raio = RAIO_AMOSTRA * ESCALA
    x0, x1 = int(cx - raio), int(cx + raio) + 1
    y0, y1 = int(cy - raio), int(cy + raio) + 1
    recorte = tinta[y0:y1, x0:x1]
    yy, xx = np.ogrid[y0:y1, x0:x1]
    disco = (xx - cx) ** 2 + (yy - cy) ** 2 <= raio**2
    return float(recorte[disco].mean() / 255)


def _ler_questao(tinta: np.ndarray, indice: int, total_alternativas: int) -> LeituraQuestao:
    preenchimento = [
        round(_preenchimento(tinta, *fr.centro_da_bolinha(indice, alternativa)), 2)
        for alternativa in range(total_alternativas)
    ]
    marcadas = [i for i, p in enumerate(preenchimento) if p >= LIMIAR_MARCADA]
    if len(marcadas) == 1:
        return LeituraQuestao(marcadas[0], "ok", preenchimento)
    if len(marcadas) > 1:
        return LeituraQuestao(None, "varias", preenchimento)
    if max(preenchimento) >= LIMIAR_DUVIDA:
        return LeituraQuestao(None, "duvida", preenchimento)
    return LeituraQuestao(None, "em_branco", preenchimento)


def ler_folha(conteudo: bytes, alternativas_por_questao: list[int]) -> LeituraFolha:
    """Lê a foto de uma folha de respostas. `alternativas_por_questao` é a
    da prova que o professor está corrigindo; quem confere se o QR é mesmo
    dessa prova é o chamador."""
    folha, identificacao = _folha_identificada(conteudo)
    tinta = _tinta(folha)
    questoes = [_ler_questao(tinta, i, total) for i, total in enumerate(alternativas_por_questao)]
    return LeituraFolha(prova_id=identificacao[0], aluno_id=identificacao[1], questoes=questoes)


def _tinta(folha: np.ndarray) -> np.ndarray:
    """Máscara 0/255 do que é tinta (escuro) na folha endireitada."""
    normalizada = _normalizar_luz(folha)
    _, tinta = cv2.threshold(normalizada, 170, 255, cv2.THRESH_BINARY_INV)
    return tinta


def _folha_identificada(conteudo: bytes) -> tuple[np.ndarray, tuple[int, int]]:
    cinza = _abrir(conteudo)
    cantos = _achar_marcas(cinza)
    # Foto girada (de lado ou de cabeça pra baixo): o canto "sup. esq." da
    # foto não é o da folha. O QR só aparece no lugar certo na rotação certa.
    for giro in range(4):
        folha = _endireitar(cinza, np.roll(cantos, -giro, axis=0))
        identificacao = _ler_qr(folha)
        if identificacao:
            return folha, identificacao
    raise QrIlegivel

