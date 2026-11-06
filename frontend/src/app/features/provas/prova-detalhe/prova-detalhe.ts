import { DatePipe } from '@angular/common';
import { Component, DestroyRef, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';

import { SELO_STATUS } from '../../../core/status-prova';
import { mensagemDoBackend } from '../../../core/http-erro';
import { AuthService } from '../../../core/services/auth.service';
import { ProvasService } from '../../../core/services/provas.service';
import { ProvaDetalhe as Prova } from '../../../models/prova.model';
import { Icone } from '../../../shared/icone/icone';

// Espelha TAMANHO_MAXIMO_MATERIAL do backend só pra avisar antes do upload;
// quem recusa de verdade é o servidor (413/415, conferindo os bytes).
const TAMANHO_MAXIMO_PDF = 10 * 1024 * 1024;
// O "clique de novo para apagar" desarma sozinho depois disso.
const DESARMAR_APAGAR_MS = 5000;

@Component({
  selector: 'app-prova-detalhe',
  standalone: true,
  imports: [DatePipe, RouterLink, Icone],
  templateUrl: './prova-detalhe.html',
})
export class ProvaDetalhe implements OnInit, OnDestroy {
  readonly seloStatus = SELO_STATUS;
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  readonly letras = 'ABCDE';

  prova = signal<Prova | null>(null);
  carregando = signal(true);
  naoEncontrada = signal(false);
  erro = signal('');
  confirmandoRemocao = signal(false);

  enviandoPdf = signal(false);
  erroPdf = signal('');

  gerandoImpressao = signal<'folhas-resposta' | 'caderno' | null>(null);
  erroImpressao = signal('');

  gerandoVersaoB = signal(false);
  erroVersaoB = signal('');
  // 403 do Free: em vez de erro, o convite pro Pro.
  versaoBSoPro = signal(false);
  versaoBGerada = signal<Prova | null>(null);

  aprovando = signal(false);
  // 403 de quem não é coordenador: o convite pro plano Escola.
  aprovarSoEscola = signal(false);
  aprovadaAgora = signal(false);
  erroAprovar = signal('');

  private timerApagar?: ReturnType<typeof setTimeout>;

  constructor(
    private readonly provasService: ProvasService,
    readonly authService: AuthService,
    private readonly router: Router,
  ) {}

  ngOnInit(): void {
    // paramMap: a versão B navega pra outra prova reaproveitando o componente.
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
    this.erro.set('');
    this.erroPdf.set('');
    this.erroVersaoB.set('');
    this.versaoBSoPro.set(false);
    this.versaoBGerada.set(null);
    this.aprovarSoEscola.set(false);
    this.aprovadaAgora.set(false);
    this.erroAprovar.set('');
    this.cancelarRemocao();
    this.provasService.ver(id).subscribe({
      next: (prova) => {
        this.prova.set(prova);
        this.carregando.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        // Prova de outro professor também dá 404 (não 403): pra quem não é
        // dono, ela simplesmente não existe.
        this.prova.set(null);
        this.naoEncontrada.set(erro.status === 404);
        this.erro.set(erro.status === 404 ? '' : 'Não foi possível carregar a prova.');
        this.carregando.set(false);
      },
    });
  }

  get ehPro(): boolean {
    return this.authService.temPapelMinimo('professor_pro');
  }

  get ehCoordenacao(): boolean {
    return this.authService.temPapelMinimo('coordenador');
  }

  aprovar(): void {
    const p = this.prova();
    if (!p) return;
    // Aparece pra todos com prova pronta: fora do plano Escola o backend
    // responde 403 e a tela mostra o convite.
    this.aprovando.set(true);
    this.aprovarSoEscola.set(false);
    this.erroAprovar.set('');
    this.provasService.aprovar(p.id).subscribe({
      next: (aprovada) => {
        this.prova.set(aprovada);
        this.aprovadaAgora.set(true);
        this.aprovando.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        if (erro.status === 403) {
          this.aprovarSoEscola.set(true);
        } else {
          this.erroAprovar.set(mensagemDoBackend(erro, 'Não foi possível aprovar a prova.'));
        }
        this.aprovando.set(false);
      },
    });
  }

  remover(): void {
    const p = this.prova();
    if (!p) return;
    // Dois cliques em vez de confirm(): o primeiro só arma o botão.
    if (!this.confirmandoRemocao()) {
      this.confirmandoRemocao.set(true);
      this.timerApagar = setTimeout(() => this.confirmandoRemocao.set(false), DESARMAR_APAGAR_MS);
      return;
    }
    clearTimeout(this.timerApagar);
    this.provasService.remover(p.id).subscribe({
      next: () => this.router.navigate(['/app/provas']),
      error: (erro: HttpErrorResponse) => {
        this.erro.set(mensagemDoBackend(erro, 'Não foi possível apagar a prova.'));
        this.confirmandoRemocao.set(false);
      },
    });
  }

  cancelarRemocao(): void {
    clearTimeout(this.timerApagar);
    this.confirmandoRemocao.set(false);
  }

  imprimir(tipo: 'folhas-resposta' | 'caderno'): void {
    const p = this.prova();
    if (!p) return;
    // A aba abre já no clique (antes da resposta) pra o navegador não tratar
    // como pop-up; o PDF entra nela quando chegar.
    const aba = window.open('', '_blank');
    this.gerandoImpressao.set(tipo);
    this.erroImpressao.set('');
    this.provasService.baixarPdf(p.id, tipo).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        if (aba) aba.location.href = url;
        else window.location.href = url;
        // A aba já carregou o PDF; libera a memória depois.
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
        this.gerandoImpressao.set(null);
      },
      error: (erro: HttpErrorResponse) => {
        aba?.close();
        // Erro com responseType blob vem como Blob: lê o detail do JSON dentro.
        const lerDetalhe = erro.error instanceof Blob ? erro.error.text() : Promise.resolve('');
        lerDetalhe.then((texto) => {
          let detalhe = '';
          try {
            detalhe = JSON.parse(texto).detail ?? '';
          } catch {
            // corpo não era JSON
          }
          this.erroImpressao.set(typeof detalhe === 'string' && detalhe ? detalhe : 'Não foi possível gerar o PDF.');
          this.gerandoImpressao.set(null);
        });
      },
    });
  }

  gerarVersaoB(): void {
    const p = this.prova();
    if (!p) return;
    // O botão aparece pra todos de propósito: no Free o backend responde
    // 403 e a mensagem dele vira o convite pro plano Pro.
    this.gerandoVersaoB.set(true);
    this.erroVersaoB.set('');
    this.versaoBSoPro.set(false);
    this.versaoBGerada.set(null);
    this.provasService.gerarVersaoB(p.id).subscribe({
      next: (nova) => {
        this.gerandoVersaoB.set(false);
        this.versaoBGerada.set(nova);
      },
      error: (erro: HttpErrorResponse) => {
        if (erro.status === 403) {
          this.versaoBSoPro.set(true);
        } else {
          this.erroVersaoB.set(mensagemDoBackend(erro, 'Não foi possível gerar a versão B.'));
        }
        this.gerandoVersaoB.set(false);
      },
    });
  }

  escolherPdf(evento: Event): void {
    const input = evento.target as HTMLInputElement;
    const arquivo = input.files?.[0];
    input.value = ''; // permite escolher o mesmo arquivo de novo depois de um erro
    const p = this.prova();
    if (!arquivo || !p) return;

    this.erroPdf.set('');
    if (arquivo.size > TAMANHO_MAXIMO_PDF) {
      this.erroPdf.set('O PDF precisa ter até 10 MB.');
      return;
    }
    this.enviandoPdf.set(true);
    this.provasService.enviarMaterial(p.id, arquivo).subscribe({
      next: (atualizada) => {
        this.prova.set(atualizada);
        this.enviandoPdf.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        this.erroPdf.set(mensagemDoBackend(erro, 'Não foi possível enviar o PDF.'));
        this.enviandoPdf.set(false);
      },
    });
  }

  abrirPdf(): void {
    const p = this.prova();
    if (!p) return;
    // A URL é pré-assinada e expira: pede uma nova a cada clique. A aba é
    // aberta já no clique (antes da resposta) pra o navegador não tratar
    // como pop-up.
    const aba = window.open('', '_blank');
    this.provasService.abrirMaterial(p.id).subscribe({
      next: (material) => {
        if (aba) aba.location.href = material.url;
        else window.location.href = material.url;
      },
      error: (erro: HttpErrorResponse) => {
        aba?.close();
        this.erroPdf.set(mensagemDoBackend(erro, 'Não foi possível abrir o PDF.'));
      },
    });
  }

  removerPdf(): void {
    const p = this.prova();
    if (!p) return;
    this.provasService.removerMaterial(p.id).subscribe({
      next: () => this.prova.set({ ...p, material_nome: null }),
      error: (erro: HttpErrorResponse) =>
        this.erroPdf.set(mensagemDoBackend(erro, 'Não foi possível remover o PDF.')),
    });
  }
}
