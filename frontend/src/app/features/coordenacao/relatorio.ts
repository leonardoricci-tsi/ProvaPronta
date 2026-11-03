import { Component, OnInit, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterLink } from '@angular/router';

import { mensagemDoBackend } from '../../core/http-erro';
import { CoordenacaoService } from '../../core/services/coordenacao.service';
import { RelatorioCoordenacao } from '../../models/coordenacao.model';
import { Icone } from '../../shared/icone/icone';

@Component({
  selector: 'app-relatorio',
  standalone: true,
  imports: [RouterLink, Icone],
  templateUrl: './relatorio.html',
})
export class Relatorio implements OnInit {
  private readonly coordenacaoService = inject(CoordenacaoService);

  relatorio = signal<RelatorioCoordenacao | null>(null);
  carregando = signal(true);
  erro = signal('');

  ngOnInit(): void {
    this.coordenacaoService.relatorio().subscribe({
      next: (relatorio) => {
        this.relatorio.set(relatorio);
        this.carregando.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        // O guard da rota já esconde a tela de quem não é coordenador; o
        // 403 aqui só acontece se o papel mudou com a tela aberta.
        this.erro.set(mensagemDoBackend(erro, 'Não foi possível carregar o relatório.'));
        this.carregando.set(false);
      },
    });
  }

  /** Largura da barra do assunto, proporcional ao que tem mais questões. */
  largura(questoes: number): string {
    const maior = Math.max(1, ...(this.relatorio()?.assuntos.map((a) => a.questoes) ?? [1]));
    return `${Math.round((questoes / maior) * 100)}%`;
  }
}
