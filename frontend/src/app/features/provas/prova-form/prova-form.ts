import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { mensagemDoBackend } from '../../../core/http-erro';
import { ProvasService } from '../../../core/services/provas.service';
import { TurmasService } from '../../../core/services/turmas.service';
import { ProvaPayload, QuestaoPayload, StatusProva } from '../../../models/prova.model';
import { Turma } from '../../../models/turma.model';
import { Icone } from '../../../shared/icone/icone';

// Espelham app/schemas/prova.py (o backend recusa com 422 de qualquer jeito).
const MIN_ALTERNATIVAS = 2;
const MAX_ALTERNATIVAS = 5;
const MAX_QUESTOES = 100;

interface QuestaoEditavel extends QuestaoPayload {
  // Só pro @for não recriar os campos ao reordenar.
  chave: number;
}

let proximaChave = 1;

function questaoVazia(): QuestaoEditavel {
  return { chave: proximaChave++, enunciado: '', alternativas: ['', '', '', ''], resposta_correta: 0, assunto: null };
}

@Component({
  selector: 'app-prova-form',
  standalone: true,
  imports: [FormsModule, RouterLink, Icone],
  templateUrl: './prova-form.html',
})
export class ProvaForm implements OnInit {
  private readonly route = inject(ActivatedRoute);

  readonly letras = 'ABCDE';
  readonly maxAlternativas = MAX_ALTERNATIVAS;
  readonly minAlternativas = MIN_ALTERNATIVAS;

  // null = criando; número = editando essa prova.
  provaId: number | null = null;
  turmas = signal<Turma[]>([]);
  carregando = signal(true);
  salvando = signal(false);
  erro = signal('');
  bateuLimite = signal(false);
  falhouAoCarregar = signal(false);
  // Os erros por campo só aparecem depois da primeira tentativa de salvar.
  tentouSalvar = signal(false);

  turmaId = 0;
  titulo = '';
  dataAplicacao = '';
  status: StatusProva = 'rascunho';
  questoes: QuestaoEditavel[] = [questaoVazia()];

  constructor(
    private readonly provasService: ProvasService,
    private readonly turmasService: TurmasService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    this.provaId = id ? Number(id) : null;
    this.turmaId = Number(this.route.snapshot.queryParamMap.get('turma')) || 0;

    this.turmasService.listar().subscribe({
      next: (turmas) => {
        if (!this.turmaId && turmas.length > 0) this.turmaId = turmas[0].id;
        this.turmas.set(turmas);
        if (this.provaId === null) this.carregando.set(false);
      },
      error: () => this.falhar('Não foi possível carregar as turmas.'),
    });

    if (this.provaId !== null) {
      this.provasService.ver(this.provaId).subscribe({
        next: (prova) => {
          this.turmaId = prova.turma.id;
          this.titulo = prova.titulo;
          this.dataAplicacao = prova.data_aplicacao ?? '';
          this.status = prova.status;
          this.questoes = prova.questoes.map((q) => ({
            chave: proximaChave++,
            enunciado: q.enunciado,
            alternativas: [...q.alternativas],
            resposta_correta: q.resposta_correta,
            assunto: q.assunto,
          }));
          this.carregando.set(false);
        },
        error: (erro: HttpErrorResponse) =>
          this.falhar(erro.status === 404 ? 'Prova não encontrada.' : 'Não foi possível carregar a prova.'),
      });
    }
  }

  private falhar(mensagem: string): void {
    this.erro.set(mensagem);
    this.falhouAoCarregar.set(true);
    this.carregando.set(false);
  }

  adicionarQuestao(): void {
    if (this.questoes.length < MAX_QUESTOES) this.questoes.push(questaoVazia());
  }

  removerQuestao(indice: number): void {
    this.questoes.splice(indice, 1);
  }

  moverQuestao(indice: number, direcao: -1 | 1): void {
    const destino = indice + direcao;
    if (destino < 0 || destino >= this.questoes.length) return;
    [this.questoes[indice], this.questoes[destino]] = [this.questoes[destino], this.questoes[indice]];
  }

  adicionarAlternativa(q: QuestaoEditavel): void {
    if (q.alternativas.length < MAX_ALTERNATIVAS) q.alternativas.push('');
  }

  removerAlternativa(q: QuestaoEditavel, indice: number): void {
    if (q.alternativas.length <= MIN_ALTERNATIVAS) return;
    q.alternativas.splice(indice, 1);
    // O gabarito aponta por índice: acompanha a remoção. Se a removida era
    // a certa, fica sem gabarito (-1) até o professor marcar outra — nunca
    // escolhe uma no lugar dele.
    if (q.resposta_correta === indice) q.resposta_correta = -1;
    else if (q.resposta_correta > indice) q.resposta_correta--;
  }

  semEnunciado(q: QuestaoEditavel): boolean {
    return !q.enunciado.trim();
  }

  alternativaVazia(q: QuestaoEditavel): boolean {
    return q.alternativas.some((a) => !a.trim());
  }

  semCorreta(q: QuestaoEditavel): boolean {
    return q.resposta_correta < 0;
  }

  questaoInvalida(q: QuestaoEditavel): boolean {
    return this.semEnunciado(q) || this.alternativaVazia(q) || this.semCorreta(q);
  }

  /** O que falta preencher, pra mostrar na barra de salvar antes de
   * mandar pro backend (que recusaria com 422 de qualquer jeito). */
  pendencias(): string[] {
    const faltas: string[] = [];
    if (!this.turmaId) faltas.push('turma');
    if (!this.titulo.trim()) faltas.push('título');
    this.questoes.forEach((q, i) => {
      if (this.semEnunciado(q)) faltas.push(`enunciado da questão ${i + 1}`);
      if (this.alternativaVazia(q)) faltas.push(`alternativas da questão ${i + 1}`);
      if (this.semCorreta(q)) faltas.push(`alternativa correta da questão ${i + 1}`);
    });
    if (this.status === 'pronta' && this.questoes.length === 0) faltas.push('ao menos 1 questão (prova pronta)');
    return faltas;
  }

  salvar(): void {
    if (this.pendencias().length > 0) {
      this.tentouSalvar.set(true);
      return;
    }
    const dados: ProvaPayload = {
      turma_id: this.turmaId,
      titulo: this.titulo.trim(),
      data_aplicacao: this.dataAplicacao || null,
      status: this.status,
      questoes: this.questoes.map(({ chave, ...q }) => ({
        ...q,
        enunciado: q.enunciado.trim(),
        alternativas: q.alternativas.map((a) => a.trim()),
        assunto: q.assunto?.trim() || null,
      })),
    };
    this.salvando.set(true);
    this.erro.set('');
    const pedido =
      this.provaId === null ? this.provasService.criar(dados) : this.provasService.editar(this.provaId, dados);
    pedido.subscribe({
      next: (prova) => this.router.navigate(['/app/provas', prova.id]),
      error: (erro: HttpErrorResponse) => {
        // 403 na criação = limite de provas do plano Free.
        this.bateuLimite.set(erro.status === 403);
        this.erro.set(mensagemDoBackend(erro, 'Não foi possível salvar a prova.'));
        this.salvando.set(false);
      },
    });
  }
}
