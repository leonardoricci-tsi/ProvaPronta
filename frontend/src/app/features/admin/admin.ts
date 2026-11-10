import { DatePipe } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';

import { SELO_PAPEL } from '../../core/papeis';
import { AdminService } from '../../core/services/admin.service';
import { AdminUsuario, EventoAuditoria, ResumoAdmin } from '../../models/admin.model';
import { Icone } from '../../shared/icone/icone';

type Aba = 'visao' | 'usuarios' | 'eventos';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [DatePipe, Icone],
  templateUrl: './admin.html',
})
export class Admin implements OnInit {
  readonly PAPEIS = Object.keys(SELO_PAPEL);
  readonly SELO_PAPEL = SELO_PAPEL;

  abaAtiva = signal<Aba>('visao');

  // Planos na ordem da escada (papel do RBAC = plano).
  readonly PLANOS_RESUMO = [
    { papel: 'professor', nome: 'Free' },
    { papel: 'professor_pro', nome: 'Professor Pro' },
    { papel: 'coordenador', nome: 'Escola' },
    { papel: 'admin', nome: 'Admin' },
  ];

  resumo = signal<ResumoAdmin | null>(null);
  carregandoResumo = signal(true);
  erroResumo = signal('');

  usuarios = signal<AdminUsuario[]>([]);
  eventos = signal<EventoAuditoria[]>([]);
  carregandoUsuarios = signal(true);
  carregandoEventos = signal(true);
  erroEventos = signal('');

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.carregarResumo();
    this.carregarUsuarios();
    this.carregarEventos();
  }

  private readonly formatoReais = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

  reais(centavos: number): string {
    return this.formatoReais.format(centavos / 100);
  }

  carregarResumo(): void {
    this.carregandoResumo.set(true);
    this.erroResumo.set('');
    this.adminService.resumo().subscribe({
      next: (resumo) => {
        this.resumo.set(resumo);
        this.carregandoResumo.set(false);
      },
      error: () => {
        this.erroResumo.set('Não foi possível montar a visão geral agora.');
        this.carregandoResumo.set(false);
      },
    });
  }

  private carregarUsuarios(): void {
    this.carregandoUsuarios.set(true);
    this.adminService.listarUsuarios().subscribe({
      next: (usuarios) => {
        this.usuarios.set(usuarios);
        this.carregandoUsuarios.set(false);
      },
      error: () => this.carregandoUsuarios.set(false),
    });
  }

  carregarEventos(): void {
    this.carregandoEventos.set(true);
    this.erroEventos.set('');
    this.adminService.listarEventos().subscribe({
      next: (eventos) => {
        this.eventos.set(eventos);
        this.carregandoEventos.set(false);
      },
      error: () => {
        this.erroEventos.set('Não foi possível ler os eventos do log-service.');
        this.carregandoEventos.set(false);
      },
    });
  }

  alterarPapel(usuario: AdminUsuario, novoPapel: string): void {
    if (novoPapel === usuario.role) {
      return;
    }
    const papelAnterior = usuario.role;
    this.usuarios.update((atual) =>
      atual.map((u) => (u.id === usuario.id ? { ...u, role: novoPapel } : u)),
    );
    this.adminService.alterarPapel(usuario.id, novoPapel).subscribe({
      error: () => {
        // reverte pro papel real se a promoção falhar (ex: 403 se o token expirou)
        this.usuarios.update((atual) =>
          atual.map((u) => (u.id === usuario.id ? { ...u, role: papelAnterior } : u)),
        );
      },
    });
  }
}
