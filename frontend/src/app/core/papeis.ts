// Selo de cada papel na tela (o papel do JWT é o plano). Só aparência:
// quem decide permissão é o backend.
export const SELO_PAPEL: Record<string, { texto: string; classe: string }> = {
  professor: { texto: 'Plano Free', classe: 'selo selo-free' },
  professor_pro: { texto: 'Professor Pro', classe: 'selo selo-pro' },
  coordenador: { texto: 'Escola', classe: 'selo selo-escola' },
  admin: { texto: 'Admin', classe: 'selo selo-gabarito' },
};
