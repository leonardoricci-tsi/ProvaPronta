from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PastaIn(BaseModel):
    nome: str = Field(min_length=1, max_length=150, examples=["1º ano — Matemática — 1º bimestre"])


class MaterialOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pasta_id: int
    nome: str
    tamanho_bytes: int
    criado_em: datetime


class PastaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    criado_em: datetime
    total_materiais: int
    # Os PDFs vêm junto: a biblioteca de um professor é pequena, e a tela de
    # gerar questões precisa da árvore inteira pra escolher pasta ou PDF.
    materiais: list[MaterialOut]


class LinkMaterialOut(BaseModel):
    nome: str
    # URL pré-assinada, temporária — gerada a cada pedido, nunca gravada.
    url: str
