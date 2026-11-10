import { Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import { CheckoutResposta, PlanoPago, PortalResposta, StatusPremium } from '../../models/premium.model';

@Injectable({ providedIn: 'root' })
export class PremiumService {
  // Plano pago do usuário LOGADO, compartilhado entre o header (anel no
  // avatar) e a página de planos. É só pra tela: o que vale de verdade é o
  // papel, conferido pelo backend em cada rota (403).
  private readonly _status = signal<StatusPremium | null>(null);
  readonly status = this._status.asReadonly();

  constructor(private readonly http: HttpClient) {}

  carregarStatus(): Observable<StatusPremium> {
    return this.http.get<StatusPremium>('/premium/status').pipe(tap((s) => this._status.set(s)));
  }

  limpar(): void {
    this._status.set(null);
  }

  // O backend devolve a URL da página de pagamento HOSPEDADA pelo Stripe —
  // o cartão é digitado lá, nunca neste site.
  abrirCheckout(plano: PlanoPago): Observable<CheckoutResposta> {
    return this.http.post<CheckoutResposta>('/premium/checkout', { plano });
  }

  // Portal do cliente do Stripe: trocar de plano, atualizar o cartão,
  // cancelar. O que mudar lá chega no backend pelos webhooks.
  abrirPortal(): Observable<PortalResposta> {
    return this.http.post<PortalResposta>('/premium/portal', {});
  }
}
