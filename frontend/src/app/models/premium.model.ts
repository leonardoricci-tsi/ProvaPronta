export interface StatusPremium {
  premium: boolean;
  // Plano pago ativo (professor_pro / coordenador), ou null no gratuito.
  plano: string | null;
}

export interface CheckoutResposta {
  checkout_url: string;
}

export type PlanoPago = 'professor_pro' | 'coordenador';
