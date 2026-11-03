import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../core/services/auth.service';
import { TemaService } from '../../core/services/tema.service';
import { Icone } from '../../shared/icone/icone';
import { Logo } from '../../shared/logo/logo';
import { PLANOS } from '../planos/planos';

@Component({
  selector: 'app-landing',
  standalone: true,
  imports: [RouterLink, Icone, Logo],
  templateUrl: './landing.html',
})
export class Landing implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);
  readonly temaService = inject(TemaService);

  // Mesmos planos da tela /app/planos — preço num lugar só.
  readonly planos = PLANOS;
  readonly ano = new Date().getFullYear();

  ngOnInit(): void {
    // Quem já está logado vai direto pras provas.
    if (this.authService.isAuthenticated()) {
      this.router.navigate(['/app/provas']);
    }
  }
}
