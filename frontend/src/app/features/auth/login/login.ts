import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../../../core/services/auth.service';
import { Icone } from '../../../shared/icone/icone';
import { Logo } from '../../../shared/logo/logo';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [FormsModule, RouterLink, Icone, Logo],
  templateUrl: './login.html',
})
export class Login {
  email = '';
  senha = '';
  erro = signal('');
  carregando = signal(false);

  constructor(
    private readonly authService: AuthService,
    private readonly router: Router,
  ) {}

  entrar(): void {
    this.erro.set('');
    this.carregando.set(true);

    this.authService.login({ email: this.email, senha: this.senha }).subscribe({
      next: () => {
        this.carregando.set(false);
        this.router.navigate(['/app/provas']);
      },
      error: (erro) => {
        this.carregando.set(false);
        this.erro.set(erro?.error?.detail ?? 'Não foi possível entrar.');
      },
    });
  }
}
