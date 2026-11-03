"""Geração de questões de múltipla escolha a partir do PDF da apostila.

O texto sai do PDF aqui mesmo (pypdf) e vai para um modelo de linguagem por
uma API no formato da OpenAI (`POST {base}/chat/completions`) — hoje o
Groq; trocar de provedor é só configuração (`LLM_*`). O que volta é
**sugestão**: cada questão é validada com as mesmas regras do editor
(`QuestaoIn`) e nada é gravado — o professor revisa e salva.
"""

import io
import json
import logging

import httpx
from pydantic import ValidationError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.config import get_settings
from app.schemas.prova import QuestaoIn

logger = logging.getLogger(__name__)

# Corta o texto pra caber no contexto do modelo com folga (e no limite de
# tokens por minuto do plano gratuito do Groq). Uma apostila de várias
# páginas passa disso; o começo do material é o que entra.
MAX_CARACTERES_TEXTO = 15_000
# Menos que isso não dá pra tirar questão de verdade (PDF escaneado, só
# imagem, costuma devolver texto vazio).
MIN_CARACTERES_TEXTO = 200

PROMPT_SISTEMA = """Você é um professor experiente da educação básica brasileira que \
elabora provas de múltipla escolha. Responda SOMENTE com um objeto JSON válido, sem \
texto antes ou depois, no formato:
{"questoes": [{"enunciado": "...", "alternativas": ["...", "...", "...", "..."], \
"resposta_correta": 0, "assunto": "..."}]}
Regras:
- Use apenas informações que estão no material fornecido; não invente fatos.
- Cada questão tem exatamente 4 alternativas, uma única correta.
- "resposta_correta" é o índice (0 a 3) da alternativa correta; varie a posição.
- As alternativas erradas devem ser plausíveis para quem não estudou.
- Não use "todas as anteriores" nem "nenhuma das anteriores".
- "assunto" é o tema da questão em até 4 palavras.
- Escreva em português do Brasil, com enunciados curtos e claros."""


class GeracaoIndisponivel(Exception):
    """Recurso desligado (sem chave configurada) — vira 503."""


class FalhaNaGeracao(Exception):
    """O provedor de IA falhou ou devolveu algo inaproveitável — vira 502."""


class PdfSemTexto(Exception):
    """PDF sem texto extraível (escaneado, protegido, corrompido) — vira 422."""


def _texto_do_pdf(conteudo_pdf: bytes) -> str:
    """Texto corrido do PDF (até o teto geral). PDF ilegível ou só imagem
    devolve "" — quem chama decide se é erro."""
    try:
        leitor = PdfReader(io.BytesIO(conteudo_pdf))
        partes = []
        total = 0
        for pagina in leitor.pages:
            texto = (pagina.extract_text() or "").strip()
            if not texto:
                continue
            partes.append(texto)
            total += len(texto)
            if total >= MAX_CARACTERES_TEXTO:
                break
    except (PdfReadError, ValueError, KeyError, TypeError):
        return ""
    return " ".join(" ".join(partes).split())[:MAX_CARACTERES_TEXTO]


def _repartir(textos: list[str], orcamento: int) -> list[str]:
    """Divide o orçamento de caracteres entre os textos: cada um ganha a
    mesma fatia, e o que um texto curto não usa vai pros outros — assim
    todo PDF escolhido entra no material, não só o primeiro."""
    cotas = [0] * len(textos)
    restantes = [i for i, t in enumerate(textos) if t]
    sobra = orcamento
    while restantes and sobra > 0:
        fatia = max(1, sobra // len(restantes))
        proximos = []
        for i in restantes:
            falta = len(textos[i]) - cotas[i]
            ganho = min(fatia, falta, sobra)
            cotas[i] += ganho
            sobra -= ganho
            if cotas[i] < len(textos[i]):
                proximos.append(i)
        restantes = proximos
    return [t[:c] for t, c in zip(textos, cotas)]


def extrair_texto(conteudo_pdf: bytes) -> str:
    return extrair_texto_de_varios([("material.pdf", conteudo_pdf)])


def extrair_texto_de_varios(arquivos: list[tuple[str, bytes]]) -> str:
    """Junta o texto de um ou mais PDFs (nome, bytes), cada um com um
    cabeçalho com o nome do arquivo, dentro do teto de caracteres."""
    textos = [_texto_do_pdf(conteudo) for _, conteudo in arquivos]
    if not any(textos) and arquivos:
        # Nenhum legível: distingue "não li" de "li e não tem texto".
        raise PdfSemTexto(
            "Não foi possível ler o texto do PDF"
            if len(arquivos) == 1
            else "Nenhum dos PDFs escolhidos tem texto legível"
        )
    cabecalhos = [f"[{nome}] " if len(arquivos) > 1 else "" for nome, _ in arquivos]
    orcamento = MAX_CARACTERES_TEXTO - sum(len(c) for c in cabecalhos)
    partes = [
        cabecalho + trecho
        for cabecalho, trecho in zip(cabecalhos, _repartir(textos, orcamento))
        if trecho
    ]
    texto = "\n\n".join(partes)
    if sum(len(t) for t in textos) < MIN_CARACTERES_TEXTO:
        raise PdfSemTexto(
            "O PDF não tem texto suficiente para gerar questões (PDF escaneado vira imagem, sem texto)"
        )
    return texto


def _pedido(texto: str, quantidade: int, disciplina: str | None) -> dict:
    settings = get_settings()
    contexto = f" da disciplina {disciplina}" if disciplina else ""
    return {
        "model": settings.llm_model,
        "temperature": 0.4,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT_SISTEMA},
            {
                "role": "user",
                "content": (
                    f"Crie {quantidade} questões de múltipla escolha{contexto} "
                    f"com base no material abaixo.\n\nMATERIAL:\n{texto}"
                ),
            },
        ],
    }


def _questoes_validas(bruto: object, quantidade: int) -> list[QuestaoIn]:
    """Fica só com o que passa nas regras do editor; descarta o resto em
    vez de derrubar a geração inteira por uma questão malformada."""
    itens = bruto.get("questoes") if isinstance(bruto, dict) else None
    if not isinstance(itens, list):
        return []
    validas = []
    for item in itens:
        if not isinstance(item, dict):
            continue
        try:
            validas.append(
                QuestaoIn(
                    enunciado=str(item.get("enunciado", "")).strip(),
                    alternativas=[str(a).strip() for a in item.get("alternativas") or []],
                    resposta_correta=item.get("resposta_correta"),
                    assunto=(str(item["assunto"]).strip()[:100] or None) if item.get("assunto") else None,
                )
            )
        except (ValidationError, TypeError, ValueError):
            continue
    return validas[:quantidade]


def gerar_questoes(texto: str, quantidade: int, disciplina: str | None = None) -> list[QuestaoIn]:
    settings = get_settings()
    if not settings.llm_api_key:
        raise GeracaoIndisponivel("Geração de questões com IA não configurada neste ambiente")

    try:
        resposta = httpx.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            json=_pedido(texto, quantidade, disciplina),
            timeout=settings.llm_timeout_segundos,
        )
    except httpx.HTTPError as erro:
        raise FalhaNaGeracao("O serviço de IA não respondeu. Tente de novo em instantes.") from erro

    if resposta.status_code == 429:
        raise FalhaNaGeracao("Limite de uso da IA atingido. Tente de novo em um minuto.")
    if resposta.status_code >= 400:
        # Corpo do erro só no log do servidor: pode ecoar detalhes da conta.
        logger.warning("IA respondeu %s: %s", resposta.status_code, resposta.text[:500])
        raise FalhaNaGeracao("O serviço de IA recusou o pedido. Tente de novo em instantes.")

    try:
        conteudo = resposta.json()["choices"][0]["message"]["content"]
        questoes = _questoes_validas(json.loads(conteudo), quantidade)
    except (KeyError, IndexError, TypeError, ValueError) as erro:
        raise FalhaNaGeracao("A IA devolveu uma resposta em formato inesperado.") from erro

    if not questoes:
        raise FalhaNaGeracao("A IA não devolveu questões válidas. Tente de novo.")
    return questoes
