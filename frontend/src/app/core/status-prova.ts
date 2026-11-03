import { StatusProva } from '../models/prova.model';

// Selo de cada situação da prova, igual em todas as telas.
export const SELO_STATUS: Record<StatusProva, { texto: string; classe: string }> = {
  rascunho: { texto: 'Rascunho', classe: 'selo selo-rascunho' },
  pronta: { texto: 'Pronta', classe: 'selo selo-pronta' },
  aprovada: { texto: 'Aprovada', classe: 'selo selo-aprovada' },
};
