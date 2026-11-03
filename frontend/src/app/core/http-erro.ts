import { HttpErrorResponse } from '@angular/common/http';

/** Mensagem do `detail` do FastAPI, se der pra mostrar. Erro de validação
 * (422) vem como lista: mostra a primeira. */
export function mensagemDoBackend(erro: HttpErrorResponse, padrao: string): string {
  const detalhe = erro.error?.detail;
  if (typeof detalhe === 'string') {
    return detalhe;
  }
  if (Array.isArray(detalhe) && typeof detalhe[0]?.msg === 'string') {
    return detalhe[0].msg.replace(/^Value error, /, '');
  }
  return padrao;
}
