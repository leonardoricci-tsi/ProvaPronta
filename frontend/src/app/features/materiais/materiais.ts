import { DecimalPipe } from '@angular/common';
import { Component, OnDestroy, OnInit, WritableSignal, inject, signal } from '@angular/core';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule, NgForm } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { mensagemDoBackend } from '../../core/http-erro';
import { AuthService } from '../../core/services/auth.service';
import { BibliotecaService } from '../../core/services/biblioteca.service';
import { MaterialBiblioteca, Pasta } from '../../models/biblioteca.model';
import { Icone } from '../../shared/icone/icone';

// Espelham o backend só pra avisar antes do envio; quem recusa de verdade
// é a API (413/415/403).
const TAMANHO_MAXIMO_PDF = 10 * 1024 * 1024;
const MAX_ARQUIVOS_POR_ENVIO = 10;
const LIMITE_MATERIAIS_FREE = 3;
const DESARMAR_APAGAR_MS = 5000;

@Component({
  selector: 'app-materiais',
  standalone: true,
  imports: [DecimalPipe, FormsModule, RouterLink, Icone],
  templateUrl: './materiais.html',
})
export class Materiais implements OnInit, OnDestroy {
  private readonly bibliotecaService = inject(BibliotecaService);
  private readonly authService = inject(AuthService);

  readonly limiteFree = LIMITE_MATERIAIS_FREE;

  pastas = signal<Pasta[]>([]);
  carregando = signal(true);
  erroLista = signal('');

  novaPasta = '';
  criando = signal(false);
  erroNovaPasta = signal('');

  // Estado por pasta (id → valor).
  enviando = signal<Record<number, boolean>>({});
  erroPasta = signal<Record<number, string>>({});
  bateuLimite = signal<Record<number, boolean>>({});
  renomeando = signal<number | null>(null);
  nomeRascunho = '';
  confirmandoApagar = signal<number | null>(null);
  private timerApagar?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    this.carregar();
  }

  ngOnDestroy(): void {
    clearTimeout(this.timerApagar);
  }

  get ehFree(): boolean {
    return !this.authService.temPapelMinimo('professor_pro');
  }

  get totalPdfs(): number {
    return this.pastas().reduce((soma, p) => soma + p.total_materiais, 0);
  }

  private carregar(): void {
    this.bibliotecaService.listar().subscribe({
      next: (pastas) => {
        this.pastas.set(pastas);
        this.carregando.set(false);
      },
      error: () => {
        this.erroLista.set('Não foi possível carregar a biblioteca.');
        this.carregando.set(false);
      },
    });
  }

  private marcar<T>(sinal: WritableSignal<Record<number, T>>, id: number, valor: T): void {
    sinal.update((atual) => ({ ...atual, [id]: valor }));
  }

  private trocarPasta(pasta: Pasta): void {
    this.pastas.update((lista) =>
      lista.map((p) => (p.id === pasta.id ? pasta : p)).sort((a, b) => a.nome.localeCompare(b.nome)),
    );
  }

  criarPasta(form: NgForm): void {
    if (form.invalid) return;
    this.criando.set(true);
    this.erroNovaPasta.set('');
    this.bibliotecaService.criarPasta(this.novaPasta.trim()).subscribe({
      next: (pasta) => {
        this.pastas.update((lista) => [...lista, pasta].sort((a, b) => a.nome.localeCompare(b.nome)));
        this.novaPasta = '';
        form.resetForm();
        this.criando.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        this.erroNovaPasta.set(mensagemDoBackend(erro, 'Não foi possível criar a pasta.'));
        this.criando.set(false);
      },
    });
  }

  escolherPdfs(pasta: Pasta, evento: Event): void {
    const input = evento.target as HTMLInputElement;
    const arquivos = Array.from(input.files ?? []);
    input.value = ''; // permite escolher os mesmos arquivos de novo depois de um erro
    if (arquivos.length === 0) return;

    this.marcar(this.erroPasta, pasta.id, '');
    this.marcar(this.bateuLimite, pasta.id, false);
    if (arquivos.length > MAX_ARQUIVOS_POR_ENVIO) {
      this.marcar(this.erroPasta, pasta.id, `Envie no máximo ${MAX_ARQUIVOS_POR_ENVIO} PDFs por vez.`);
      return;
    }
    const grande = arquivos.find((a) => a.size > TAMANHO_MAXIMO_PDF);
    if (grande) {
      this.marcar(this.erroPasta, pasta.id, `"${grande.name}" passa de 10 MB.`);
      return;
    }

    this.marcar(this.enviando, pasta.id, true);
    this.bibliotecaService.enviarPdfs(pasta.id, arquivos).subscribe({
      next: (novos) => {
        const materiais = [...pasta.materiais, ...novos].sort((a, b) => a.nome.localeCompare(b.nome));
        this.trocarPasta({ ...pasta, materiais, total_materiais: materiais.length });
        this.marcar(this.enviando, pasta.id, false);
      },
      error: (erro: HttpErrorResponse) => {
        // 403 = limite do Free (3 PDFs): o backend explica, a tela linka os planos.
        this.marcar(this.bateuLimite, pasta.id, erro.status === 403);
        this.marcar(this.erroPasta, pasta.id, mensagemDoBackend(erro, 'Não foi possível enviar os PDFs.'));
        this.marcar(this.enviando, pasta.id, false);
      },
    });
  }

  abrir(material: MaterialBiblioteca): void {
    // URL pré-assinada que expira: pede uma nova a cada clique. A aba abre
    // já no clique pra o navegador não tratar como pop-up.
    const aba = window.open('', '_blank');
    this.bibliotecaService.abrir(material.id).subscribe({
      next: ({ url }) => {
        if (aba) aba.location.href = url;
        else window.location.href = url;
      },
      error: (erro: HttpErrorResponse) => {
        aba?.close();
        this.marcar(this.erroPasta, material.pasta_id, mensagemDoBackend(erro, 'Não foi possível abrir o PDF.'));
      },
    });
  }

  removerPdf(pasta: Pasta, material: MaterialBiblioteca): void {
    this.bibliotecaService.remover(material.id).subscribe({
      next: () => {
        const materiais = pasta.materiais.filter((m) => m.id !== material.id);
        this.trocarPasta({ ...pasta, materiais, total_materiais: materiais.length });
      },
      error: (erro: HttpErrorResponse) =>
        this.marcar(this.erroPasta, pasta.id, mensagemDoBackend(erro, 'Não foi possível remover o PDF.')),
    });
  }

  comecarRenomear(pasta: Pasta): void {
    this.nomeRascunho = pasta.nome;
    this.renomeando.set(pasta.id);
  }

  salvarNome(pasta: Pasta): void {
    const nome = this.nomeRascunho.trim();
    if (!nome) return;
    this.bibliotecaService.renomearPasta(pasta.id, nome).subscribe({
      next: (atualizada) => {
        this.trocarPasta(atualizada);
        this.renomeando.set(null);
      },
      error: (erro: HttpErrorResponse) =>
        this.marcar(this.erroPasta, pasta.id, mensagemDoBackend(erro, 'Não foi possível renomear.')),
    });
  }

  apagarPasta(pasta: Pasta): void {
    // Dois cliques em vez de confirm(): o primeiro só arma o botão.
    if (this.confirmandoApagar() !== pasta.id) {
      clearTimeout(this.timerApagar);
      this.confirmandoApagar.set(pasta.id);
      this.timerApagar = setTimeout(() => this.confirmandoApagar.set(null), DESARMAR_APAGAR_MS);
      return;
    }
    clearTimeout(this.timerApagar);
    this.confirmandoApagar.set(null);
    this.bibliotecaService.removerPasta(pasta.id).subscribe({
      next: () => this.pastas.update((lista) => lista.filter((p) => p.id !== pasta.id)),
      error: (erro: HttpErrorResponse) =>
        this.marcar(this.erroPasta, pasta.id, mensagemDoBackend(erro, 'Não foi possível apagar a pasta.')),
    });
  }
}
