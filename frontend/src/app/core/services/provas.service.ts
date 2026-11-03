import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import {
  FontesGeracao,
  Material,
  Prova,
  ProvaDetalhe,
  ProvaPayload,
  QuestoesGeradas,
} from '../../models/prova.model';

@Injectable({ providedIn: 'root' })
export class ProvasService {
  constructor(private readonly http: HttpClient) {}

  listar(turmaId?: number): Observable<Prova[]> {
    const params = turmaId ? new HttpParams().set('turma_id', turmaId) : undefined;
    return this.http.get<Prova[]>('/provas', { params });
  }

  ver(id: number): Observable<ProvaDetalhe> {
    return this.http.get<ProvaDetalhe>(`/provas/${id}`);
  }

  criar(dados: ProvaPayload): Observable<ProvaDetalhe> {
    return this.http.post<ProvaDetalhe>('/provas', dados);
  }

  editar(id: number, dados: Partial<ProvaPayload>): Observable<ProvaDetalhe> {
    return this.http.patch<ProvaDetalhe>(`/provas/${id}`, dados);
  }

  remover(id: number): Observable<void> {
    return this.http.delete<void>(`/provas/${id}`);
  }

  // Só Professor Pro pra cima: o Free recebe 403 do backend.
  gerarVersaoB(id: number): Observable<ProvaDetalhe> {
    return this.http.post<ProvaDetalhe>(`/provas/${id}/versao-b`, {});
  }

  // Só coordenador pra cima (plano Escola): professor e Pro recebem 403.
  aprovar(id: number): Observable<ProvaDetalhe> {
    return this.http.post<ProvaDetalhe>(`/provas/${id}/aprovar`, {});
  }

  // Plano Pro: a IA lê os PDFs escolhidos e sugere questões (nada é gravado).
  gerarQuestoes(id: number, quantidade: number, fontes: FontesGeracao): Observable<QuestoesGeradas> {
    return this.http.post<QuestoesGeradas>(`/provas/${id}/gerar-questoes`, { quantidade, ...fontes });
  }

  enviarMaterial(id: number, arquivo: File): Observable<ProvaDetalhe> {
    // Sem Content-Type manual: o navegador monta o multipart com o boundary.
    const corpo = new FormData();
    corpo.append('arquivo', arquivo);
    return this.http.post<ProvaDetalhe>(`/provas/${id}/material`, corpo);
  }

  abrirMaterial(id: number): Observable<Material> {
    return this.http.get<Material>(`/provas/${id}/material`);
  }

  removerMaterial(id: number): Observable<void> {
    return this.http.delete<void>(`/provas/${id}/material`);
  }
}
