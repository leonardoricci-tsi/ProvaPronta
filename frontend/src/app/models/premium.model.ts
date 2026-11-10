export interface StatusPremium {
  premium: boolean;
  // Plano pago ativo (professor_pro / coordenador), ou null no gratuito.
  plano: string | null;
  // Status da assinatura no Stripe (active, past_due, canceled...), ou null
  // pra quem nunca assinou. past_due = a cobrança do mês foi recusada.
  status: string | null;
  // Tem assinatura no Stripe pra abrir no portal ("Gerenciar assinatura").
  pode_gerenciar: boolean;
}

export interface PortalResposta {
  portal_url: string;
}

export interface CheckoutResposta {
  checkout_url: string;
}

export type PlanoPago = 'professor_pro' | 'coordenador';
