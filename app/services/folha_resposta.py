"""Folha de respostas e caderno da prova em PDF (reportlab).

A folha tem uma página por aluno: QR code com prova + aluno, grade de
bolinhas A–E e quatro marcas pretas nos cantos. A geometria (onde fica cada
marca e cada bolinha) mora aqui, em constantes e funções puras, porque a
correção por foto vai usar exatamente as mesmas posições para ler a folha:
mudar o desenho é mudar a leitura, no mesmo lugar.
"""

import io
from dataclasses import dataclass

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.colors import black, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer

LARGURA, ALTURA = A4  # 595 × 842 pontos (origem no canto inferior esquerdo)
LETRAS = "ABCDE"

# Marcas de alinhamento: quadrados pretos cheios nos 4 cantos. A foto é
# "endireitada" achando os 4 e levando-os de volta pra estas posições.
MARCA_LADO = 9 * mm
MARCA_MARGEM = 10 * mm

# QR code no canto superior direito, dentro das marcas.
QR_LADO = 32 * mm
QR_X = LARGURA - MARCA_MARGEM - MARCA_LADO - 4 * mm - QR_LADO
QR_Y = ALTURA - MARCA_MARGEM - MARCA_LADO - 2 * mm - QR_LADO

# Grade de bolinhas: até 25 questões por coluna, até 4 colunas (100 questões,
# o máximo de uma prova).
QUESTOES_POR_COLUNA = 25
MAX_COLUNAS = 4
GRADE_TOPO = ALTURA - 82 * mm  # centro da 1ª linha
GRADE_ESQUERDA = 22 * mm  # x do número da questão na 1ª coluna
LARGURA_COLUNA = 45 * mm
ALTURA_LINHA = 7.4 * mm
BOLINHA_RAIO = 2.4 * mm
DESLOCAMENTO_1A_BOLINHA = 9 * mm  # do número da questão até o centro da A
ESPACO_ENTRE_BOLINHAS = 6.6 * mm

# Conteúdo do QR: versão do formato + prova + aluno. Curto de propósito
# (QR menor, leitura mais fácil). Quem confere o dono é o servidor, na hora
# de corrigir — o QR só diz "de quem é esta folha".
PREFIXO_QR = "PP1"


def conteudo_qr(prova_id: int, aluno_id: int) -> str:
    return f"{PREFIXO_QR}:{prova_id}:{aluno_id}"


def ler_conteudo_qr(texto: str) -> tuple[int, int] | None:
    """(prova_id, aluno_id) de um QR desta folha, ou None se não for nosso."""
    partes = texto.strip().split(":")
    if len(partes) != 3 or partes[0] != PREFIXO_QR or not all(p.isdigit() for p in partes[1:]):
        return None
    return int(partes[1]), int(partes[2])


def centros_das_marcas() -> list[tuple[float, float]]:
    """Centro de cada marca, em pontos: sup. esq., sup. dir., inf. dir., inf. esq."""
    meio = MARCA_MARGEM + MARCA_LADO / 2
    return [(meio, ALTURA - meio), (LARGURA - meio, ALTURA - meio), (LARGURA - meio, meio), (meio, meio)]


def centro_da_bolinha(indice_questao: int, indice_alternativa: int) -> tuple[float, float]:
    """Centro da bolinha (x, y em pontos) da questão (0-based) e alternativa (0 = A)."""
    coluna, linha = divmod(indice_questao, QUESTOES_POR_COLUNA)
    x_numero = GRADE_ESQUERDA + coluna * LARGURA_COLUNA
    x = x_numero + DESLOCAMENTO_1A_BOLINHA + indice_alternativa * ESPACO_ENTRE_BOLINHAS
    y = GRADE_TOPO - linha * ALTURA_LINHA
    return x, y


@dataclass
class DadosFolha:
    prova_id: int
    titulo: str
    turma: str
    data_aplicacao: str | None
    aluno_id: int
    aluno_nome: str
    numero_chamada: int
    # Quantidade de alternativas de cada questão, na ordem.
    alternativas_por_questao: list[int]


def _texto_cortado(canvas: Canvas, texto: str, fonte: str, tamanho: float, largura_max: float) -> str:
    if canvas.stringWidth(texto, fonte, tamanho) <= largura_max:
        return texto
    while texto and canvas.stringWidth(texto + "…", fonte, tamanho) > largura_max:
        texto = texto[:-1]
    return texto + "…"


def _desenhar_marcas(canvas: Canvas) -> None:
    canvas.setFillColor(black)
    for cx, cy in centros_das_marcas():
        canvas.rect(cx - MARCA_LADO / 2, cy - MARCA_LADO / 2, MARCA_LADO, MARCA_LADO, stroke=0, fill=1)


def _desenhar_qr(canvas: Canvas, conteudo: str) -> None:
    widget = QrCodeWidget(conteudo, barLevel="M")
    x0, y0, x1, y1 = widget.getBounds()
    desenho = Drawing(QR_LADO, QR_LADO, transform=[QR_LADO / (x1 - x0), 0, 0, QR_LADO / (y1 - y0), 0, 0])
    desenho.add(widget)
    renderPDF.draw(desenho, canvas, QR_X, QR_Y)


def _desenhar_pagina(canvas: Canvas, dados: DadosFolha) -> None:
    _desenhar_marcas(canvas)
    _desenhar_qr(canvas, conteudo_qr(dados.prova_id, dados.aluno_id))

    esquerda = MARCA_MARGEM + MARCA_LADO + 4 * mm
    largura_texto = QR_X - esquerda - 6 * mm
    topo = ALTURA - MARCA_MARGEM - 5 * mm

    canvas.setFillColor(black)
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(esquerda, topo, "ProvaPronta · Folha de respostas")
    canvas.setFont("Helvetica-Bold", 15)
    canvas.drawString(esquerda, topo - 8 * mm, _texto_cortado(canvas, dados.titulo, "Helvetica-Bold", 15, largura_texto))
    canvas.setFont("Helvetica", 10)
    detalhe = dados.turma + (f" · Aplicação {dados.data_aplicacao}" if dados.data_aplicacao else "")
    canvas.drawString(esquerda, topo - 14 * mm, _texto_cortado(canvas, detalhe, "Helvetica", 10, largura_texto))

    # Aluno, em destaque: é o que o professor confere ao distribuir.
    canvas.setFont("Helvetica", 9)
    canvas.drawString(esquerda, topo - 23 * mm, "ALUNO")
    canvas.setFont("Helvetica-Bold", 13)
    aluno = f"{dados.numero_chamada}. {dados.aluno_nome}"
    canvas.drawString(esquerda, topo - 29 * mm, _texto_cortado(canvas, aluno, "Helvetica-Bold", 13, largura_texto))

    # Abaixo do QR (que termina ~36 mm abaixo do topo), na largura toda.
    canvas.setFont("Helvetica", 8.5)
    canvas.drawString(esquerda, topo - 41 * mm, "Preencha a bolinha inteira, com caneta preta ou azul. Uma resposta por questão.")
    canvas.drawString(esquerda, topo - 45 * mm, "Não dobre a folha nem rasure as marcas pretas dos cantos: elas servem para ler a foto.")

    # Grade: número da questão + bolinhas (só as alternativas que existem).
    for indice, total in enumerate(dados.alternativas_por_questao):
        x_numero, _ = centro_da_bolinha(indice, 0)
        x_numero -= DESLOCAMENTO_1A_BOLINHA
        _, y = centro_da_bolinha(indice, 0)
        canvas.setFillColor(black)
        canvas.setFont("Helvetica-Bold", 9)
        canvas.drawRightString(x_numero + 4 * mm, y - 1.1 * mm, f"{indice + 1:02d}")
        for alternativa in range(total):
            cx, cy = centro_da_bolinha(indice, alternativa)
            canvas.setStrokeColor(black)
            canvas.setLineWidth(0.8)
            canvas.setFillColor(white)
            canvas.circle(cx, cy, BOLINHA_RAIO, stroke=1, fill=1)
            canvas.setFillColor(black)
            canvas.setFont("Helvetica", 6.5)
            canvas.drawCentredString(cx, cy - 0.8 * mm, LETRAS[alternativa])

    canvas.setFont("Helvetica", 7.5)
    canvas.drawCentredString(
        LARGURA / 2, MARCA_MARGEM + 2 * mm, f"Prova {dados.prova_id} · Aluno {dados.aluno_id} · ProvaPronta"
    )


def gerar_folhas(folhas: list[DadosFolha]) -> bytes:
    """Um PDF com uma página por aluno."""
    saida = io.BytesIO()
    canvas = Canvas(saida, pagesize=A4)
    canvas.setTitle(f"Folhas de resposta — {folhas[0].titulo}" if folhas else "Folhas de resposta")
    canvas.setAuthor("ProvaPronta")
    for dados in folhas:
        _desenhar_pagina(canvas, dados)
        canvas.showPage()
    canvas.save()
    return saida.getvalue()


@dataclass
class QuestaoCaderno:
    enunciado: str
    alternativas: list[str]


def _escapar(texto: str) -> str:
    """Paragraph do reportlab interpreta marcação: escapa o texto do professor."""
    return texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def gerar_caderno(titulo: str, turma: str, data_aplicacao: str | None, questoes: list[QuestaoCaderno]) -> bytes:
    """O caderno da prova para imprimir: cabeçalho e questões, sem gabarito."""
    saida = io.BytesIO()
    documento = SimpleDocTemplate(
        saida,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=titulo,
        author="ProvaPronta",
    )
    estilo_titulo = ParagraphStyle("titulo", fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=2 * mm)
    estilo_info = ParagraphStyle("info", fontName="Helvetica", fontSize=10, leading=14)
    estilo_enunciado = ParagraphStyle("enunciado", fontName="Helvetica-Bold", fontSize=11, leading=15, spaceAfter=1.5 * mm)
    estilo_alternativa = ParagraphStyle("alternativa", fontName="Helvetica", fontSize=10.5, leading=14, leftIndent=6 * mm)

    historia = [
        Paragraph(_escapar(titulo), estilo_titulo),
        Paragraph(_escapar(turma + (f" · Aplicação {data_aplicacao}" if data_aplicacao else "")), estilo_info),
        Spacer(1, 4 * mm),
        Paragraph("Nome: ______________________________________________  Nº: ______", estilo_info),
        Spacer(1, 2 * mm),
        Paragraph("Marque as respostas na folha de respostas.", estilo_info),
        Spacer(1, 6 * mm),
    ]
    for numero, questao in enumerate(questoes, start=1):
        bloco = [Paragraph(f"{numero}. {_escapar(questao.enunciado)}", estilo_enunciado)]
        bloco += [
            Paragraph(f"<b>{LETRAS[i]})</b> {_escapar(alternativa)}", estilo_alternativa)
            for i, alternativa in enumerate(questao.alternativas)
        ]
        bloco.append(Spacer(1, 5 * mm))
        # Questão nunca quebra entre duas páginas.
        historia.append(KeepTogether(bloco))
    documento.build(historia)
    return saida.getvalue()
