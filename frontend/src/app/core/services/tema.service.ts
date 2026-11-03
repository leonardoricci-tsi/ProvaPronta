import { Injectable, signal } from '@angular/core';

export type Tema = 'claro' | 'escuro';

const CHAVE = 'tema';

/** Tema claro/escuro. Sem escolha salva, segue o sistema (o CSS cuida
 * disso com prefers-color-scheme); escolher grava no navegador e marca o
 * <html data-tema>, que o index.html reaplica antes do Angular subir. */
@Injectable({ providedIn: 'root' })
export class TemaService {
  private readonly _tema = signal<Tema>(this.temaInicial());
  readonly tema = this._tema.asReadonly();

  private temaInicial(): Tema {
    const salvo = document.documentElement.getAttribute('data-tema');
    if (salvo === 'claro' || salvo === 'escuro') return salvo;
    return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro';
  }

  alternar(): void {
    const novo: Tema = this._tema() === 'escuro' ? 'claro' : 'escuro';
    this._tema.set(novo);
    document.documentElement.setAttribute('data-tema', novo);
    try {
      localStorage.setItem(CHAVE, novo);
    } catch {
      // Navegação privada/armazenamento bloqueado: vale só nesta aba.
    }
  }
}
