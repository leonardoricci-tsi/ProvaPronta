// Espelha app/schemas/coordenacao.py.
export interface RelatorioCoordenacao {
  totais: { turmas: number; alunos: number; provas: number; provas_aprovadas: number; questoes: number };
  turmas: {
    id: number;
    nome: string;
    disciplina: string;
    ano_letivo: number;
    total_alunos: number;
    provas: { rascunho: number; pronta: number; aprovada: number };
    total_questoes: number;
  }[];
  assuntos: { assunto: string; questoes: number; provas: number }[];
}
