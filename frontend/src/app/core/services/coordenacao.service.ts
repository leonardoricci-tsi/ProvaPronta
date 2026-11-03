import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { RelatorioCoordenacao } from '../../models/coordenacao.model';

@Injectable({ providedIn: 'root' })
export class CoordenacaoService {
  constructor(private readonly http: HttpClient) {}

  // Só coordenador pra cima (plano Escola): professor e Pro recebem 403.
  relatorio(): Observable<RelatorioCoordenacao> {
    return this.http.get<RelatorioCoordenacao>('/coordenacao/relatorio');
  }
}
