import { Component, DestroyRef, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { mensagemDoBackend } from '../../../core/http-erro';
import { ProvasService } from '../../../core/services/provas.service';
import { TurmasService } from '../../../core/services/turmas.service';
import { Prova } from '../../../models/prova.model';
import { Aluno, TurmaDetalhe as Turma, TurmaPayload } from '../../../models/turma.model';
import { Icone } from '../../../shared/icone/icone';

// O "clique de novo para apagar" desarma sozinho depois disso.
const DESARMAR_APAGAR_MS = 5000;

@Component({
  selector: 'app-turma-detalhe',
  standalone: true,
  imports: [FormsModule, RouterLink, Icone],
  templateUrl: './turma-detalhe.html',
})
export class TurmaDetalhe implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  turma = signal<Turma | null>(null);
  provas = signal<Prova[]>([]);
  carregando = signal(true);
  naoEncontrada = signal(false);
  erro = signal('');

  editando = signal(false);
  rascunho: TurmaPayload = { nome: '', disciplina: '', escola: '', ano_letivo: 2026 };
  salvando = signal(false);
  confirmandoRemocao = signal(false);

  novoAluno = { nome: '', numero: 1 };
  erroAluno = signal('');
  adicionando = signal(false);

  private timerApagar?: ReturnType<typeof setTimeout>;

  constructor(
    private readonly turmasService: TurmasService,
    private readonly provasService: ProvasService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      this.carregar(Number(params.get('id')));
    });
  }

  ngOnDestroy(): void {
    clearTimeout(this.timerApagar);
  }

  private carregar(id: number): void {
    this.carregando.set(true);
    this.naoEncontrada.set(false);
    this.turmasService.ver(id).subscribe({
      next: (turma) => {
        this.definirTurma(turma);
        this.carregando.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        // Turma de outro professor também dá 404: pra quem não é dono, ela
        // não existe.
        this.naoEncontrada.set(erro.status === 404);
        this.erro.set(erro.status === 404 ? '' : 'Não foi possível carregar a turma.');
        this.carregando.set(false);
      },
    });
    this.provasService.listar(id).subscribe({ next: (provas) => this.provas.set(provas) });
  }

  private definirTurma(turma: Turma): void {
    this.turma.set(turma);
    const maior = Math.max(0, ...turma.alunos.map((a) => a.numero_chamada));
    this.novoAluno = { nome: '', numero: maior + 1 };
  }

  comecarEdicao(): void {
    const t = this.turma();
    if (!t) return;
    this.rascunho = { nome: t.nome, disciplina: t.disciplina, escola: t.escola ?? '', ano_letivo: t.ano_letivo };
    this.editando.set(true);
  }

  salvar(): void {
    const t = this.turma();
    if (!t) return;
    this.salvando.set(true);
    this.erro.set('');
    this.turmasService
      .editar(t.id, { ...this.rascunho, escola: this.rascunho.escola?.trim() || null })
      .subscribe({
        next: (turma) => {
          this.definirTurma(turma);
          this.editando.set(false);
          this.salvando.set(false);
        },
        error: (erro: HttpErrorResponse) => {
          this.erro.set(mensagemDoBackend(erro, 'Não foi possível salvar.'));
          this.salvando.set(false);
        },
      });
  }

  remover(): void {
    const t = this.turma();
    if (!t) return;
    // Dois cliques em vez de confirm(): o primeiro só arma o botão.
    if (!this.confirmandoRemocao()) {
      this.confirmandoRemocao.set(true);
      this.timerApagar = setTimeout(() => this.confirmandoRemocao.set(false), DESARMAR_APAGAR_MS);
      return;
    }
    clearTimeout(this.timerApagar);
    this.turmasService.remover(t.id).subscribe({
      next: () => this.router.navigate(['/app/turmas']),
      error: (erro: HttpErrorResponse) => {
        // 409 = a turma tem provas (a FK é RESTRICT).
        this.erro.set(mensagemDoBackend(erro, 'Não foi possível apagar a turma.'));
        this.cancelarRemocao();
      },
    });
  }

  cancelarRemocao(): void {
    clearTimeout(this.timerApagar);
    this.confirmandoRemocao.set(false);
  }

  adicionarAluno(): void {
    const t = this.turma();
    if (!t || !this.novoAluno.nome.trim()) return;
    this.erroAluno.set('');
    this.adicionando.set(true);
    this.turmasService.adicionarAluno(t.id, this.novoAluno.nome.trim(), this.novoAluno.numero).subscribe({
      next: (aluno) => {
        const alunos = [...t.alunos, aluno].sort((a, b) => a.numero_chamada - b.numero_chamada);
        this.definirTurma({ ...t, alunos, total_alunos: alunos.length });
        this.adicionando.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        // 409 = número de chamada repetido nesta turma.
        this.erroAluno.set(mensagemDoBackend(erro, 'Não foi possível adicionar o aluno.'));
        this.adicionando.set(false);
      },
    });
  }

  removerAluno(aluno: Aluno): void {
    const t = this.turma();
    if (!t) return;
    this.turmasService.removerAluno(t.id, aluno.id).subscribe({
      next: () => {
        const alunos = t.alunos.filter((a) => a.id !== aluno.id);
        this.definirTurma({ ...t, alunos, total_alunos: alunos.length });
      },
      error: (erro: HttpErrorResponse) =>
        this.erroAluno.set(mensagemDoBackend(erro, 'Não foi possível remover o aluno.')),
    });
  }
}
