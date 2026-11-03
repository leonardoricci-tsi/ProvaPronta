import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink } from '@angular/router';

/** Marca do ProvaPronta: o “check” da correção + o ponto do marca-texto. */
@Component({
  selector: 'app-logo',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  host: { style: 'display: contents' },
  template: `
    <a class="logo" [routerLink]="destino()" [attr.aria-label]="'ProvaPronta — ' + rotulo()">
      <svg [attr.width]="tamanho()" [attr.height]="tamanho()" viewBox="0 0 32 32" aria-hidden="true">
        <rect width="32" height="32" rx="8" fill="#2747B8"></rect>
        <path d="M8.5 16.5l4.5 4.5 8.5-9" fill="none" stroke="#FFFFFF" stroke-width="3.2"
          stroke-linecap="round" stroke-linejoin="round"></path>
        <circle cx="25" cy="7" r="3" fill="#FFE066"></circle>
      </svg>
      <span>Prova<span class="pronta">Pronta</span></span>
    </a>
  `,
})
export class Logo {
  readonly destino = input('/');
  readonly rotulo = input('início');
  readonly tamanho = input(32);
}
