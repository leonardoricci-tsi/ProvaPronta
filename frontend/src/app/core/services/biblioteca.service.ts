import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { MaterialBiblioteca, Pasta } from '../../models/biblioteca.model';
import { Material } from '../../models/prova.model';

@Injectable({ providedIn: 'root' })
export class BibliotecaService {
  constructor(private readonly http: HttpClient) {}

  // Só as pastas do usuário do token, já com os PDFs de cada uma.
  listar(): Observable<Pasta[]> {
    return this.http.get<Pasta[]>('/pastas');
  }

  criarPasta(nome: string): Observable<Pasta> {
    return this.http.post<Pasta>('/pastas', { nome });
  }

  renomearPasta(id: number, nome: string): Observable<Pasta> {
    return this.http.patch<Pasta>(`/pastas/${id}`, { nome });
  }

  removerPasta(id: number): Observable<void> {
    return this.http.delete<void>(`/pastas/${id}`);
  }

  enviarPdfs(pastaId: number, arquivos: File[]): Observable<MaterialBiblioteca[]> {
    // Sem Content-Type manual: o navegador monta o multipart com o boundary.
    const corpo = new FormData();
    arquivos.forEach((arquivo) => corpo.append('arquivos', arquivo));
    return this.http.post<MaterialBiblioteca[]>(`/pastas/${pastaId}/materiais`, corpo);
  }

  abrir(materialId: number): Observable<Material> {
    return this.http.get<Material>(`/materiais/${materialId}/link`);
  }

  remover(materialId: number): Observable<void> {
    return this.http.delete<void>(`/materiais/${materialId}`);
  }
}
