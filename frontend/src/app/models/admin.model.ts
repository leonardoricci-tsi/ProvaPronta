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
