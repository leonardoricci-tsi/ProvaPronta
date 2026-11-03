// Espelham app/schemas/turma.py.
export interface Aluno {
  id: number;
  nome: string;
  numero_chamada: number;
}

export interface TurmaPayload {
  nome: string;
  disciplina: string;
  escola: string | null;
  ano_letivo: number;
}

export interface Turma extends TurmaPayload {
  id: number;
  criado_em: string;
  total_alunos: number;
}

export interface TurmaDetalhe extends Turma {
  alunos: Aluno[];
}
