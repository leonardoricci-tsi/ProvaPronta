export interface AdminUsuario {
  id: number;
  nome: string;
  email: string;
  role: string;
  criado_em: string;
}

// Evento de auditoria do log-service (GET /admin/logs).
export interface EventoAuditoria {
  usuario_id: number;
  acao: string;
  timestamp: string;
  ip: string | null;
}

// Visão geral do negócio (GET /admin/resumo).
export interface ResumoAdmin {
  usuarios_por_plano: Record<string, number>;
  total_usuarios: number;
  assinaturas_ativas: number;
  assinaturas_ativas_por_plano: Record<string, number>;
  inadimplentes: number;
  mrr_centavos: number;
  eventos_recentes: EventoAuditoria[];
}
