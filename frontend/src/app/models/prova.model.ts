// Espelham app/schemas/prova.py.
// "aprovada" só a coordenação dá (plano Escola); o professor alterna entre
// rascunho e pronta.
export type StatusProva = 'rascunho' | 'pronta' | 'aprovada';
export type StatusEditavel = 'rascunho' | 'pronta';

export interface QuestaoPayload {
  enunciado: string;
  alternativas: string[];
  // Índice da alternativa certa (0 = A, 1 = B...).
  resposta_correta: number;
  assunto: string | null;
}

export interface Questao extends QuestaoPayload {
  id: number;
  ordem: number;
}

export interface ProvaPayload {
  turma_id: number;
  titulo: string;
  data_aplicacao: string | null;
  status: StatusEditavel;
  questoes: QuestaoPayload[];
}

export interface Prova {
  id: number;
  titulo: string;
  data_aplicacao: string | null;
  status: StatusProva;
  turma: { id: number; nome: string; disciplina: string };
  total_questoes: number;
  material_nome: string | null;
  criado_em: string;
  atualizado_em: string;
}

export interface ProvaDetalhe extends Prova {
  questoes: Questao[];
}

export interface Material {
  nome: string;
  // URL pré-assinada do Garage, temporária — pedir de novo a cada clique.
  url: string;
}

// Sugestões da IA a partir do PDF — nada é gravado até o professor salvar.
export interface QuestoesGeradas {
  questoes: QuestaoPayload[];
  fonte: string;
  fontes: string[];
}

// De onde a IA tira o conteúdo; pode combinar os três.
export interface FontesGeracao {
  pasta_ids: number[];
  material_ids: number[];
  usar_pdf_da_prova: boolean;
}
