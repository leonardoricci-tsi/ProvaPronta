import { Component, computed, inject } from '@angular/core';
import { RouterLink, RouterOutlet } from '@angular/router';

import { PremiumService } from '../../core/services/premium.service';
import { Icone } from '../../shared/icone/icone';
import { Header } from '../header/header';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, Header, Icone],
  templateUrl: './app-shell.html',
})
export class AppShell {
  private readonly premiumService = inject(PremiumService);

  // invoice.payment_failed chegou: avisa em todas as telas (o e-mail também
  // sai, mas nem todo mundo lê). O status vem do header, ao entrar.
  readonly pagamentoPendente = computed(() => this.premiumService.status()?.status === 'past_due');
}
