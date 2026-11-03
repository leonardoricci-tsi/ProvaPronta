import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { Icone } from '../../../shared/icone/icone';
import { Logo } from '../../../shared/logo/logo';

@Component({
  selector: 'app-forgot-password',
  standalone: true,
  imports: [FormsModule, RouterLink, Icone, Logo],
  templateUrl: './forgot-password.html',
})
export class ForgotPassword {
  email = '';
  mensagem = signal('');
  erro = signal('');
  carregando = signal(false);

  constructor(private readonly authService: AuthService) {}

  enviar(): void {
    this.erro.set('');
    this.mensagem.set('');
    this.carregando.set(true);

    this.authService.forgotPassword({ email: this.email }).subscribe({
      next: (resposta) => {
        this.carregando.set(false);
        this.mensagem.set(resposta.detail);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.erro.set(erro?.error?.detail ?? 'Não foi possível processar o pedido.');
      },
    });
  }
}
