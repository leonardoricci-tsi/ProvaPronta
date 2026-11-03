import { Component, ElementRef, HostListener, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { filter } from 'rxjs';

import { SELO_PAPEL } from '../../core/papeis';
import { AuthService } from '../../core/services/auth.service';
import { PremiumService } from '../../core/services/premium.service';
import { ProfileService } from '../../core/services/profile.service';
import { TemaService } from '../../core/services/tema.service';
import { Icone } from '../../shared/icone/icone';
import { Logo } from '../../shared/logo/logo';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [RouterLink, RouterLinkActive, Icone, Logo],
  templateUrl: './header.html',
})
export class Header implements OnInit {
  private readonly elemento = inject(ElementRef<HTMLElement>);
  readonly authService = inject(AuthService);
  readonly profileService = inject(ProfileService);
  readonly temaService = inject(TemaService);
  private readonly premiumService = inject(PremiumService);
  private readonly router = inject(Router);

  readonly menuAberto = signal(false);
  readonly gavetaAberta = signal(false);

  constructor() {
    // Trocar de tela fecha o menu e a gaveta do celular.
    this.router.events.pipe(filter((e) => e instanceof NavigationEnd), takeUntilDestroyed())
      .subscribe(() => this.fechar());
  }

  ngOnInit(): void {
    // O header só existe dentro da área logada (AppShell), então aqui
    // sempre há um usuário — busca a foto dele uma vez, pro avatar.
    const id = this.authService.usuarioId();
    if (id !== null) {
      this.profileService.carregarMinhaFoto(id);
      this.premiumService.carregarStatus().subscribe({ error: () => this.premiumService.limpar() });
    }
  }

  get iniciais(): string {
    const partes = (this.authService.usuario()?.nome ?? '?').trim().split(/\s+/);
    const ultima = partes.length > 1 ? partes[partes.length - 1].charAt(0) : '';
    return (partes[0].charAt(0) + ultima).toUpperCase();
  }

  get primeiroNome(): string {
    return (this.authService.usuario()?.nome ?? '').trim().split(/\s+/)[0];
  }

  get selo(): { texto: string; classe: string } {
    const papel = this.authService.usuario()?.role ?? '';
    return SELO_PAPEL[papel] ?? { texto: papel, classe: 'selo selo-free' };
  }

  alternarMenu(): void {
    this.menuAberto.update((aberto) => !aberto);
    this.gavetaAberta.set(false);
  }

  alternarGaveta(): void {
    this.gavetaAberta.update((aberta) => !aberta);
    this.menuAberto.set(false);
  }

  fechar(): void {
    this.menuAberto.set(false);
    this.gavetaAberta.set(false);
  }

  @HostListener('document:keydown.escape')
  aoApertarEsc(): void {
    this.fechar();
  }

  @HostListener('document:click', ['$event'])
  aoClicarFora(evento: MouseEvent): void {
    if (!this.elemento.nativeElement.contains(evento.target as Node)) {
      this.fechar();
    }
  }

  sair(): void {
    this.authService.logout();
    this.profileService.limparMinhaFoto();
    this.premiumService.limpar();
    this.fechar();
    this.router.navigate(['/']);
  }
}
