import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { Aluno, Turma, TurmaDetalhe, TurmaPayload } from '../../models/turma.model';

@Injectable({ providedIn: 'root' })
export class TurmasService {
  constructor(private readonly http: HttpClient) {}

  // O backend só devolve as turmas do usuário do token — não tem filtro
  // por dono aqui porque não precisa (nem deve) ter.
  listar(): Observable<Turma[]> {
    return this.http.get<Turma[]>('/turmas');
  }

  ver(id: number): Observable<TurmaDetalhe> {
    return this.http.get<TurmaDetalhe>(`/turmas/${id}`);
  }

  criar(dados: TurmaPayload): Observable<TurmaDetalhe> {
    return this.http.post<TurmaDetalhe>('/turmas', dados);
  }

  editar(id: number, dados: Partial<TurmaPayload>): Observable<TurmaDetalhe> {
    return this.http.patch<TurmaDetalhe>(`/turmas/${id}`, dados);
  }

  remover(id: number): Observable<void> {
    return this.http.delete<void>(`/turmas/${id}`);
  }

  adicionarAluno(turmaId: number, nome: string, numeroChamada: number): Observable<Aluno> {
    return this.http.post<Aluno>(`/turmas/${turmaId}/alunos`, {
      nome,
      numero_chamada: numeroChamada,
    });
  }

  removerAluno(turmaId: number, alunoId: number): Observable<void> {
    return this.http.delete<void>(`/turmas/${turmaId}/alunos/${alunoId}`);
  }
}
