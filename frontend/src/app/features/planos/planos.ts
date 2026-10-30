import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { switchMap } from 'rxjs';

import { AuthService } from '../../core/services/auth.service';
import { PremiumService } from '../../core/services/premium.service';
import { PlanoPago } from '../../models/premium.model';

// Quanto tempo esperar o webhook depois de voltar do checkout. Em teste ele
// chega em 1-3 s; passou disso, é melhor avisar do que girar pra sempre.
const INTERVALO_MS = 2000;
const TENTATIVAS = 15;

type Retorno = 'nenhum' | 'confirmando' | 'confirmado' | 'demorou' | 'cancelado';

interface Plano {
  papel: string;
  icone: string;
  nome: string;
  preco: string;
  periodo: string;
  descricao: string;
  beneficios: string[];
  destaque?: boolean;
}

// Mesmos planos da landing page. Cada plano é um papel do RBAC: Free
// (`professor`) é o gratuito (todo cadastro nasce nele), Pro e Escola são vendidos.
export const PLANOS: Plano[] = [
  {
    papel: 'professor',
    icone: '📝',
    nome: 'Free',
    preco: 'Grátis',
    periodo: '',
    descricao: 'Para experimentar com uma turma.',
    beneficios: ['1 turma (até 40 alunos)', '2 provas por mês', 'Questões de múltipla escolha', '3 PDFs de material'],
  },
  {
    papel: 'professor_pro',
    icone: '🎓',
    nome: 'Pro',
    preco: 'R$ 29,90',
    periodo: '/mês',
    descricao: 'Para o professor com várias turmas.',
    beneficios: ['Turmas e provas ilimitadas', 'Versões A/B embaralhadas', 'Banco de questões reaproveitável', 'Exportar notas em planilha'],
    destaque: true,
  },
  {
    papel: 'coordenador',
    icone: '🏫',
    nome: 'Escola',
    preco: 'R$ 199,90',
    periodo: '/mês',
    descricao: 'Para a coordenação pedagógica.',
    beneficios: ['Tudo do Pro para até 15 professores', 'Coordenador revisa e aprova a prova', 'Relatório por turma e por assunto'],
  },
];

const NIVEL: Record<string, number> = { professor: 1, professor_pro: 2, coordenador: 3, admin: 4 };

@Component({
  selector: 'app-planos',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './planos.html',
  styleUrl: './planos.css',
})
export class Planos implements OnInit, OnDestroy {
  private readonly route = inject(ActivatedRoute);
  private readonly premiumService = inject(PremiumService);
  readonly authService = inject(AuthService);

  readonly planos = PLANOS;
  readonly retorno = signal<Retorno>('nenhum');
  readonly abrindo = signal<string | null>(null);
  readonly erro = signal('');

  private timer?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    const checkout = this.route.snapshot.queryParamMap.get('checkout');
    if (checkout === 'sucesso') {
      // O navegador voltou do Stripe, mas quem confirma o pagamento é o
      // webhook — que chega por outro caminho, talvez um pouco depois.
      // Então pergunta ao backend até o plano aparecer.
      this.retorno.set('confirmando');
      this.esperarConfirmacao(TENTATIVAS);
    } else if (checkout === 'cancelado') {
      this.retorno.set('cancelado');
    }
  }

  ngOnDestroy(): void {
    clearTimeout(this.timer);
  }

  private nivelAtual(): number {
    return NIVEL[this.authService.usuario()?.role ?? ''] ?? 0;
  }

  // 'atual' | 'incluso' (plano abaixo do papel atual) | 'comprar'
  situacao(plano: Plano): 'atual' | 'incluso' | 'comprar' {
    const nivel = NIVEL[plano.papel];
    if (nivel === this.nivelAtual()) return 'atual';
    return nivel < this.nivelAtual() ? 'incluso' : 'comprar';
  }

  get nomePlanoAtual(): string {
    return PLANOS.find((p) => p.papel === this.authService.usuario()?.role)?.nome ?? 'Admin';
  }

  private esperarConfirmacao(restantes: number): void {
    this.premiumService.carregarStatus().subscribe({
      next: (status) => {
        if (status.premium) {
          // O papel mudou no banco, mas o JWT guardado ainda tem o velho:
          // pega um token novo, e o menu/rotas já liberam o plano novo.
          this.authService.renovarToken().subscribe({
            next: () => this.retorno.set('confirmado'),
            error: () => this.retorno.set('demorou'),
          });
        } else if (restantes > 1) {
          this.timer = setTimeout(() => this.esperarConfirmacao(restantes - 1), INTERVALO_MS);
        } else {
          this.retorno.set('demorou');
        }
      },
      error: () => this.retorno.set('demorou'),
    });
  }

  assinar(plano: Plano): void {
    this.erro.set('');
    this.abrindo.set(plano.papel);
    // Renova antes: se um admin mudou o papel nesse meio-tempo, o backend
    // decide com o papel atual (e recusa com 409 se já tiver o plano).
    this.authService
      .renovarToken()
      .pipe(switchMap(() => this.premiumService.abrirCheckout(plano.papel as PlanoPago)))
      .subscribe({
        // Redireciona a página inteira pro Stripe (não é rota do Angular).
        next: ({ checkout_url }) => window.location.assign(checkout_url),
        error: (erro: HttpErrorResponse) => {
          const detalhe = erro.error?.detail;
          this.erro.set(typeof detalhe === 'string' ? detalhe : 'Não foi possível abrir o pagamento.');
          this.abrindo.set(null);
        },
      });
  }
}
