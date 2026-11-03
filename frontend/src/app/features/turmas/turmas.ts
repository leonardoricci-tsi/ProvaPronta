import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule, NgForm } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { mensagemDoBackend } from '../../core/http-erro';
import { AuthService } from '../../core/services/auth.service';
import { TurmasService } from '../../core/services/turmas.service';
import { Turma } from '../../models/turma.model';
import { Icone } from '../../shared/icone/icone';

// Espelha LIMITE_TURMAS_FREE de app/services/planos.py, só pra avisar antes;
// quem barra de verdade é o 403 do backend.
const LIMITE_TURMAS_FREE = 1;

@Component({
  selector: 'app-turmas',
  standalone: true,
  imports: [FormsModule, RouterLink, Icone],
  templateUrl: './turmas.html',
})
export class Turmas implements OnInit {
  private readonly turmasService = inject(TurmasService);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  readonly limiteFree = LIMITE_TURMAS_FREE;

  turmas = signal<Turma[]>([]);
  carregando = signal(true);
  erroLista = signal('');

  salvando = signal(false);
  erro = signal('');
  // 403 = limite do plano Free: aí vale mostrar o link dos planos.
  bateuLimite = signal(false);
  nova = { nome: '', disciplina: '', escola: '', ano_letivo: new Date().getFullYear() };

  ngOnInit(): void {
    this.turmasService.listar().subscribe({
      next: (turmas) => {
        this.turmas.set(turmas);
        this.carregando.set(false);
      },
      error: () => {
        this.erroLista.set('Não foi possível carregar as turmas.');
        this.carregando.set(false);
      },
    });
  }

  get ehFree(): boolean {
    return !this.authService.temPapelMinimo('professor_pro');
  }

  get noLimite(): boolean {
    return this.ehFree && this.turmas().length >= LIMITE_TURMAS_FREE;
  }

  get resumo(): string {
    const turmas = this.turmas();
    const alunos = turmas.reduce((soma, t) => soma + t.total_alunos, 0);
    const anos = [...new Set(turmas.map((t) => t.ano_letivo))].sort().join(', ');
    if (this.ehFree) return `${turmas.length} de ${LIMITE_TURMAS_FREE} turma no plano Free · ${alunos} alunos`;
    return `${turmas.length} ${turmas.length === 1 ? 'turma' : 'turmas'} · ${alunos} alunos · ${anos}`;
  }

  criar(form: NgForm): void {
    if (form.invalid) return;
    this.salvando.set(true);
    this.erro.set('');
    this.turmasService
      .criar({ ...this.nova, escola: this.nova.escola.trim() || null })
      .subscribe({
        // Vai direto pro detalhe, onde se cadastram os alunos.
        next: (turma) => this.router.navigate(['/app/turmas', turma.id]),
        error: (erro: HttpErrorResponse) => {
          // 403 aqui é o limite do plano Free (1 turma): o backend explica.
          this.bateuLimite.set(erro.status === 403);
          this.erro.set(mensagemDoBackend(erro, 'Não foi possível criar a turma.'));
          this.salvando.set(false);
        },
      });
  }
}
