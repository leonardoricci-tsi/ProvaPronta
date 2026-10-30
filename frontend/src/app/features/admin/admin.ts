import { CommonModule } from '@angular/common';
import { Component, OnInit, signal } from '@angular/core';

import { AdminService } from '../../core/services/admin.service';
import { AdminComentario, AdminFavorito, AdminUsuario } from '../../models/admin.model';

type Aba = 'usuarios' | 'comentarios' | 'favoritos';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './admin.html',
  styleUrl: './admin.css',
})
export class Admin implements OnInit {
  readonly PAPEIS = ['professor', 'professor_pro', 'coordenador', 'admin'];

  abaAtiva = signal<Aba>('usuarios');

  usuarios = signal<AdminUsuario[]>([]);
  comentarios = signal<AdminComentario[]>([]);
  favoritos = signal<AdminFavorito[]>([]);

  carregandoUsuarios = signal(true);
  carregandoComentarios = signal(true);
  carregandoFavoritos = signal(true);

  constructor(private readonly adminService: AdminService) {}

  ngOnInit(): void {
    this.carregarUsuarios();
    this.carregarComentarios();
    this.carregarFavoritos();
  }

  trocarAba(aba: Aba): void {
    this.abaAtiva.set(aba);
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

  private carregarComentarios(): void {
    this.carregandoComentarios.set(true);
    this.adminService.listarComentarios().subscribe({
      next: (comentarios) => {
        this.comentarios.set(comentarios);
        this.carregandoComentarios.set(false);
      },
      error: () => this.carregandoComentarios.set(false),
    });
  }

  private carregarFavoritos(): void {
    this.carregandoFavoritos.set(true);
    this.adminService.listarFavoritos().subscribe({
      next: (favoritos) => {
        this.favoritos.set(favoritos);
        this.carregandoFavoritos.set(false);
      },
      error: () => this.carregandoFavoritos.set(false),
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

  removerComentario(comentario: AdminComentario): void {
    this.comentarios.update((atual) => atual.filter((c) => c.id !== comentario.id));
    this.adminService.removerComentario(comentario.id).subscribe({
      error: () => this.carregarComentarios(),
    });
  }

  removerFavorito(favorito: AdminFavorito): void {
    this.favoritos.update((atual) => atual.filter((f) => f.id !== favorito.id));
    this.adminService.removerFavorito(favorito.id).subscribe({
      error: () => this.carregarFavoritos(),
    });
  }
}
