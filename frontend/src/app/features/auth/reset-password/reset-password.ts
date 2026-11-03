import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { Icone } from '../../../shared/icone/icone';
import { Logo } from '../../../shared/logo/logo';

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [FormsModule, RouterLink, Icone, Logo],
  templateUrl: './reset-password.html',
})
export class ResetPassword {
  token = '';
  novaSenha = '';
  sucesso = signal(false);
  erro = signal('');
  carregando = signal(false);

  constructor(
    private readonly authService: AuthService,
    private readonly route: ActivatedRoute,
  ) {
    this.token = this.route.snapshot.queryParamMap.get('token') ?? '';
  }

  redefinir(): void {
    this.erro.set('');
    this.carregando.set(true);

    this.authService.resetPassword({ token: this.token, nova_senha: this.novaSenha }).subscribe({
      next: () => {
        this.carregando.set(false);
        this.sucesso.set(true);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.erro.set(erro?.error?.detail ?? 'Não foi possível redefinir a senha.');
      },
    });
  }
}
