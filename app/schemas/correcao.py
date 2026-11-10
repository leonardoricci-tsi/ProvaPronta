from typing import Literal

from pydantic import BaseModel, Field


class AlunoDaFolha(BaseModel):
    id: int
    nome: str
    numero_chamada: int


class RespostaLida(BaseModel):
    numero: int = Field(description="Número da questão na folha (1, 2, 3...)")
    questao_id: int
    marcada: int | None = Field(description="Alternativa lida (0 = A); null se em branco ou ambígua")
    situacao: Literal["ok", "em_branco", "varias", "duvida"] = Field(
        description="ok = uma marcada; em_branco; varias = mais de uma pintada; duvida = pintou pouco"
    )
    correta: int = Field(description="Alternativa do gabarito (0 = A)")
    acertou: bool
    preenchimento: list[float] = Field(description="Fração pintada de cada alternativa, 0–1")


class LeituraFolhaOut(BaseModel):
    """Resultado da leitura: ainda não é nota lançada — o professor confere
    (principalmente as questões em `conferir`) e confirma."""

    prova_id: int
    aluno: AlunoDaFolha
    respostas: list[RespostaLida]
    acertos: int
    total: int
    nota_recomendada: float = Field(description="0 a 10, uma casa decimal: acertos / total × 10")
    conferir: list[int] = Field(description="Números das questões em branco, com mais de uma marcada ou em dúvida")
