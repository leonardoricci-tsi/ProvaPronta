from pydantic import BaseModel


class ProvasPorStatusOut(BaseModel):
    rascunho: int = 0
    pronta: int = 0
    aprovada: int = 0


class TurmaRelatorioOut(BaseModel):
    id: int
    nome: str
    disciplina: str
    ano_letivo: int
    total_alunos: int
    provas: ProvasPorStatusOut
    total_questoes: int


class AssuntoRelatorioOut(BaseModel):
    # Questão sem assunto entra como "Sem assunto".
    assunto: str
    questoes: int
    provas: int


class TotaisRelatorioOut(BaseModel):
    turmas: int
    alunos: int
    provas: int
    provas_aprovadas: int
    questoes: int


class RelatorioCoordenacaoOut(BaseModel):
    totais: TotaisRelatorioOut
    turmas: list[TurmaRelatorioOut]
    assuntos: list[AssuntoRelatorioOut]
