import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { AdminUsuario, EventoAuditoria, ResumoAdmin } from '../../models/admin.model';

@Injectable({ providedIn: 'root' })
export class AdminService {
  constructor(private readonly http: HttpClient) {}

  listarUsuarios(): Observable<AdminUsuario[]> {
    return this.http.get<AdminUsuario[]>('/auth/admin/users');
  }

  alterarPapel(usuarioId: number, role: string): Observable<AdminUsuario> {
    return this.http.patch<AdminUsuario>(`/auth/admin/users/${usuarioId}/role`, { role });
  }

  resumo(): Observable<ResumoAdmin> {
    return this.http.get<ResumoAdmin>('/admin/resumo');
  }

  listarEventos(limite = 100): Observable<EventoAuditoria[]> {
    return this.http.get<EventoAuditoria[]>('/admin/logs', { params: new HttpParams().set('limit', limite) });
  }
}
