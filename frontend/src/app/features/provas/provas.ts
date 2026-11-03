import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { SELO_STATUS } from '../../core/status-prova';
import { ProvasService } from '../../core/services/provas.service';
import { TurmasService } from '../../core/services/turmas.service';
import { Prova } from '../../models/prova.model';
import { Turma } from '../../models/turma.model';
import { Icone } from '../../shared/icone/icone';

@Component({
  selector: 'app-provas',
  standalone: true,
  imports: [DatePipe, FormsModule, RouterLink, Icone],
  templateUrl: './provas.html',
})
export class Provas implements OnInit {
  readonly seloStatus = SELO_STATUS;
  provas = signal<Prova[]>([]);
  turmas = signal<Turma[]>([]);
  carregando = signal(true);
  // Só depois das turmas dá pra escolher entre os dois estados vazios.
  turmasCarregadas = signal(false);
  erro = signal('');
  // 0 = todas as turmas.
  turmaFiltro = 0;

  constructor(
    private readonly provasService: ProvasService,
    private readonly turmasService: TurmasService,
  ) {}

  ngOnInit(): void {
    this.turmasService.listar().subscribe({
      next: (turmas) => {
        this.turmas.set(turmas);
        this.turmasCarregadas.set(true);
      },
      error: () => this.turmasCarregadas.set(true),
    });
    this.carregar();
  }

  get nomeTurmaFiltro(): string {
    const turma = this.turmas().find((t) => t.id === this.turmaFiltro);
    return turma ? `${turma.nome} — ${turma.disciplina}` : '';
  }

  get resumo(): string {
    const total = this.provas().length;
    const provas = total === 1 ? '1 prova' : `${total} provas`;
    if (this.turmaFiltro) return `${provas} em ${this.nomeTurmaFiltro}`;
    const turmas = this.turmas().length;
    return `${provas} em ${turmas === 1 ? '1 turma' : turmas + ' turmas'}`;
  }

  carregar(): void {
    this.carregando.set(true);
    this.provasService.listar(this.turmaFiltro || undefined).subscribe({
      next: (provas) => {
        this.provas.set(provas);
        this.carregando.set(false);
      },
      error: () => {
        this.erro.set('Não foi possível carregar as provas.');
        this.carregando.set(false);
      },
    });
  }
}
