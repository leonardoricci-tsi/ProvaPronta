from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AlunoIn(BaseModel):
    nome: str = Field(min_length=1, max_length=150)
    numero_chamada: int = Field(ge=1, le=999)


class AlunoOut(AlunoIn):
    model_config = ConfigDict(from_attributes=True)

    id: int


class TurmaIn(BaseModel):
    # Sem usuario_id de propósito: o dono vem do JWT, nunca do corpo.
    nome: str = Field(min_length=1, max_length=100, examples=["1º A"])
    disciplina: str = Field(min_length=1, max_length=100, examples=["Biologia"])
    escola: str | None = Field(default=None, max_length=150)
    ano_letivo: int = Field(ge=2000, le=2100, examples=[2026])


class TurmaUpdateIn(BaseModel):
    """PATCH: só o que vier no corpo muda."""

    nome: str | None = Field(default=None, min_length=1, max_length=100)
    disciplina: str | None = Field(default=None, min_length=1, max_length=100)
    escola: str | None = Field(default=None, max_length=150)
    ano_letivo: int | None = Field(default=None, ge=2000, le=2100)


class TurmaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    disciplina: str
    escola: str | None
    ano_letivo: int
    criado_em: datetime
    total_alunos: int


class TurmaDetalheOut(TurmaOut):
    alunos: list[AlunoOut]
