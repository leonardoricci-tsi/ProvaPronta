import { Favorite } from './favorite.model';

export interface Profile {
  usuario_id: number;
  nome: string;
  bio: string;
  // URL pré-assinada do Garage, temporária — não guardar, sempre usar a
  // que veio na última resposta.
  foto_url: string | null;
  eh_meu: boolean;
  // Plano pago ativo (atividade 7): professor_pro / coordenador, ou null.
  plano: string | null;
  favoritos: Favorite[];
}
