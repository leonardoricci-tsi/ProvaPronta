// Espelha app/schemas/biblioteca.py.
export interface MaterialBiblioteca {
  id: number;
  pasta_id: number;
  nome: string;
  tamanho_bytes: number;
  criado_em: string;
}

export interface Pasta {
  id: number;
  nome: string;
  criado_em: string;
  total_materiais: number;
  materiais: MaterialBiblioteca[];
}
