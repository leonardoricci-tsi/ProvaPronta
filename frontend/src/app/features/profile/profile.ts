import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { HttpErrorResponse } from '@angular/common/http';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';

import { SELO_PAPEL } from '../../core/papeis';
import { AuthService } from '../../core/services/auth.service';
import { ProfileService } from '../../core/services/profile.service';
import { Profile as Perfil } from '../../models/profile.model';
import { Icone } from '../../shared/icone/icone';
import { PLANOS } from '../planos/planos';

// Espelham os limites do backend (app/services/imagem.py) só pra avisar
// antes de gastar um upload — quem recusa de verdade é o servidor
// (413/415), que confere os bytes, não o tipo que o navegador declara.
const TAMANHO_MAXIMO_BYTES = 2 * 1024 * 1024;
const TIPOS_ACEITOS = ['image/jpeg', 'image/png', 'image/webp'];
const BIO_MAXIMO = 280;

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [FormsModule, RouterLink, Icone],
  templateUrl: './profile.html',
})
export class Profile implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);

  readonly bioMaximo = BIO_MAXIMO;
  readonly tiposAceitos = TIPOS_ACEITOS.join(',');

  perfil = signal<Perfil | null>(null);
  carregando = signal(true);
  erro = signal('');

  bioRascunho = signal('');
  salvandoBio = signal(false);
  bioSalva = signal(false);

  enviandoFoto = signal(false);
  erroFoto = signal('');

  constructor(
    private readonly profileService: ProfileService,
    readonly authService: AuthService,
  ) {}

  ngOnInit(): void {
    // paramMap (não snapshot): ir de /app/perfil/2 pra /app/perfil/3
    // reaproveita o mesmo componente, então precisa reagir à troca de id.
    this.route.paramMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe((params) => {
      const id = Number(params.get('id') ?? this.authService.usuarioId());
      this.carregar(id);
    });
  }

  private carregar(usuarioId: number): void {
    this.carregando.set(true);
    this.erro.set('');
    this.bioSalva.set(false);
    this.erroFoto.set('');
    this.profileService.ver(usuarioId).subscribe({
      next: (perfil) => {
        this.perfil.set(perfil);
        this.bioRascunho.set(perfil.bio ?? '');
        this.carregando.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        this.perfil.set(null);
        this.erro.set(
          erro.status === 404 ? 'Esse usuário não existe.' : 'Não foi possível carregar o perfil.',
        );
        this.carregando.set(false);
      },
    });
  }

  get iniciais(): string {
    const partes = (this.perfil()?.nome ?? '?').trim().split(/\s+/);
    const ultima = partes.length > 1 ? partes[partes.length - 1].charAt(0) : '';
    return (partes[0].charAt(0) + ultima).toUpperCase();
  }

  get selo(): { texto: string; classe: string } {
    // O próprio perfil usa o papel do JWT (pega o Free também); o de outra
    // pessoa só sabe do plano pago.
    const p = this.perfil();
    const papel = p?.eh_meu ? this.authService.usuario()?.role : p?.plano;
    return SELO_PAPEL[papel ?? 'professor'] ?? SELO_PAPEL['professor'];
  }

  get nomePlano(): string {
    return PLANOS.find((p) => p.papel === this.authService.usuario()?.role)?.nome ?? 'Admin';
  }

  descartarBio(): void {
    this.bioRascunho.set(this.perfil()?.bio ?? '');
    this.bioSalva.set(false);
  }

  salvarBio(): void {
    const perfil = this.perfil();
    if (!perfil) return;

    this.salvandoBio.set(true);
    this.bioSalva.set(false);
    this.profileService.editarBio(perfil.usuario_id, this.bioRascunho().trim()).subscribe({
      next: (atualizado) => {
        this.perfil.set(atualizado);
        this.bioRascunho.set(atualizado.bio ?? '');
        this.salvandoBio.set(false);
        this.bioSalva.set(true);
      },
      error: (erro: HttpErrorResponse) => {
        this.erro.set(this.mensagemDoBackend(erro, 'Não foi possível salvar a bio.'));
        this.salvandoBio.set(false);
      },
    });
  }

  escolherFoto(evento: Event): void {
    const input = evento.target as HTMLInputElement;
    const arquivo = input.files?.[0];
    input.value = ''; // permite escolher o mesmo arquivo de novo depois de um erro
    const perfil = this.perfil();
    if (!arquivo || !perfil) return;

    this.erroFoto.set('');
    if (!TIPOS_ACEITOS.includes(arquivo.type)) {
      this.erroFoto.set('Escolha uma imagem JPEG, PNG ou WEBP.');
      return;
    }
    if (arquivo.size > TAMANHO_MAXIMO_BYTES) {
      this.erroFoto.set('A imagem precisa ter até 2 MB.');
      return;
    }

    this.enviandoFoto.set(true);
    this.profileService.enviarFoto(perfil.usuario_id, arquivo).subscribe({
      next: (atualizado) => {
        this.perfil.set(atualizado);
        this.enviandoFoto.set(false);
      },
      error: (erro: HttpErrorResponse) => {
        this.erroFoto.set(this.mensagemDoBackend(erro, 'Não foi possível enviar a foto.'));
        this.enviandoFoto.set(false);
      },
    });
  }

  private mensagemDoBackend(erro: HttpErrorResponse, padrao: string): string {
    const detalhe = erro.error?.detail;
    return typeof detalhe === 'string' ? detalhe : padrao;
  }
}
