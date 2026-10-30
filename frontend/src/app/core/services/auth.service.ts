import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, switchMap, tap } from 'rxjs';

import {
  ForgotPasswordPayload,
  LoginPayload,
  RegisterPayload,
  ResetPasswordPayload,
  TokenResponse,
} from '../../models/auth.model';

const TOKEN_KEY = 'token';
const NOME_KEY = 'nome';
const EMAIL_KEY = 'email';
const ROLE_KEY = 'role';

export interface UsuarioLogado {
  nome: string;
  email: string;
  role: string;
}

// Espelha app/auth/dependencies.py::NIVEL_PAPEL, só pra decidir o que
// mostrar na tela — quem garante permissão de verdade é sempre o backend
// (403 mesmo chamando o endpoint direto), isso aqui é só UX.
const NIVEL_PAPEL: Record<string, number> = {
  professor: 1,
  professor_pro: 2,
  coordenador: 3,
  admin: 4,
};

function idDoToken(token: string | null): number | null {
  if (!token) {
    return null;
  }
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const id = Number(JSON.parse(atob(payload)).sub);
    return Number.isInteger(id) ? id : null;
  } catch {
    return null;
  }
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly _token = signal<string | null>(localStorage.getItem(TOKEN_KEY));
  private readonly _usuario = signal<UsuarioLogado | null>(this.lerUsuarioSalvo());

  readonly isAuthenticated = computed(() => this._token() !== null);
  // Id do usuário logado, lido do `sub` do JWT (não precisa de chamada nem
  // de mais um item no localStorage). Só pra montar o link "meu perfil" —
  // o backend confere a identidade de novo, do token assinado, em toda
  // requisição.
  readonly usuarioId = computed(() => idDoToken(this._token()));
  readonly usuario = this._usuario.asReadonly();

  constructor(private readonly http: HttpClient) {}

  private lerUsuarioSalvo(): UsuarioLogado | null {
    const nome = localStorage.getItem(NOME_KEY);
    const email = localStorage.getItem(EMAIL_KEY);
    const role = localStorage.getItem(ROLE_KEY);
    return nome && email && role ? { nome, email, role } : null;
  }

  getToken(): string | null {
    return this._token();
  }

  temPapelMinimo(papelMinimo: string): boolean {
    const papel = this._usuario()?.role;
    if (!papel) {
      return false;
    }
    return (NIVEL_PAPEL[papel] ?? 0) >= (NIVEL_PAPEL[papelMinimo] ?? Infinity);
  }

  isAdmin(): boolean {
    return this._usuario()?.role === 'admin';
  }

  login(payload: LoginPayload): Observable<UsuarioLogado> {
    return this.http.post<TokenResponse>('/auth/login', payload).pipe(
      tap((resposta) => this._token.set(resposta.access_token)),
      tap((resposta) => localStorage.setItem(TOKEN_KEY, resposta.access_token)),
      switchMap(() => this.carregarPerfil()),
    );
  }

  // Token novo com o papel atual do banco (atividade 7): o papel viaja
  // dentro do JWT, então depois que um plano pago troca o papel, o token
  // guardado ainda diz o papel velho — sem isso, só relogando.
  renovarToken(): Observable<UsuarioLogado> {
    return this.http.post<TokenResponse>('/auth/refresh', {}).pipe(
      tap((resposta) => this._token.set(resposta.access_token)),
      tap((resposta) => localStorage.setItem(TOKEN_KEY, resposta.access_token)),
      switchMap(() => this.carregarPerfil()),
    );
  }

  register(payload: RegisterPayload): Observable<UsuarioLogado> {
    return this.http.post<TokenResponse>('/auth/register', payload).pipe(
      tap((resposta) => this._token.set(resposta.access_token)),
      tap((resposta) => localStorage.setItem(TOKEN_KEY, resposta.access_token)),
      switchMap(() => this.carregarPerfil()),
    );
  }

  private carregarPerfil(): Observable<UsuarioLogado> {
    return this.http.get<UsuarioLogado>('/auth/me').pipe(
      tap((usuario) => {
        localStorage.setItem(NOME_KEY, usuario.nome);
        localStorage.setItem(EMAIL_KEY, usuario.email);
        localStorage.setItem(ROLE_KEY, usuario.role);
        this._usuario.set(usuario);
      }),
    );
  }

  forgotPassword(payload: ForgotPasswordPayload): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>('/auth/forgot-password', payload);
  }

  resetPassword(payload: ResetPasswordPayload): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>('/auth/reset-password', payload);
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(NOME_KEY);
    localStorage.removeItem(EMAIL_KEY);
    localStorage.removeItem(ROLE_KEY);
    this._token.set(null);
    this._usuario.set(null);
  }
}
