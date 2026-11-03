from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# O que o professor pode escrever. "aprovada" fica de fora de propósito: só
# a coordenação aprova, pela rota própria — mandar status "aprovada" no
# corpo dá 422, então não há como se autoaprovar pela API.
StatusEditavel = Literal["rascunho", "pronta"]
# O que a API devolve.
StatusProva = Literal["rascunho", "pronta", "aprovada"]


class QuestaoIn(BaseModel):
    enunciado: str = Field(min_length=1, max_length=5000)
    alternativas: list[str] = Field(min_length=2, max_length=5, examples=[["Ribossomo", "Mitocôndria"]])
    # Índice da alternativa certa (0 = A, 1 = B...).
    resposta_correta: int = Field(ge=0)
    assunto: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def _gabarito_aponta_pra_uma_alternativa(self) -> "QuestaoIn":
        if any(not alternativa.strip() for alternativa in self.alternativas):
            raise ValueError("Nenhuma alternativa pode ficar vazia")
        if self.resposta_correta >= len(self.alternativas):
            raise ValueError("resposta_correta precisa apontar pra uma das alternativas")
        return self


class QuestaoOut(QuestaoIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ordem: int


class ProvaIn(BaseModel):
    # Sem usuario_id: o dono vem do JWT. A turma tem que ser do mesmo dono
    # (senão 404, como se não existisse).
    turma_id: int
    titulo: str = Field(min_length=1, max_length=200, examples=["Avaliação bimestral — Citologia"])
    data_aplicacao: date | None = None
    status: StatusEditavel = "rascunho"
    questoes: list[QuestaoIn] = Field(default_factory=list, max_length=100)


class ProvaUpdateIn(BaseModel):
    """PATCH: só o que vier no corpo muda. `questoes`, se vier, substitui
    a lista inteira (na ordem enviada)."""

    turma_id: int | None = None
    titulo: str | None = Field(default=None, min_length=1, max_length=200)
    data_aplicacao: date | None = None
    status: StatusEditavel | None = None
    questoes: list[QuestaoIn] | None = Field(default=None, max_length=100)


class TurmaResumoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    disciplina: str


class ProvaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    data_aplicacao: date | None
    status: StatusProva
    turma: TurmaResumoOut
    total_questoes: int
    material_nome: str | None
    criado_em: datetime
    atualizado_em: datetime


class ProvaDetalheOut(ProvaOut):
    # Gabarito incluso: este endpoint só responde pro dono da prova.
    questoes: list[QuestaoOut]


class MaterialOut(BaseModel):
    nome: str
    # URL pré-assinada, temporária — gerada a cada pedido, nunca gravada.
    url: str
