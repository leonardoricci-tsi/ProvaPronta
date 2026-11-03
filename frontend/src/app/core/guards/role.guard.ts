import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';

/** Guard de UX: esconde a rota de quem não tem o papel mínimo. A permissão
 * de verdade é sempre checada no backend (403) — isso aqui só evita que
 * alguém sem o papel certo caia numa tela quebrada. */
export function roleGuard(papelMinimo: string): CanActivateFn {
  return () => {
    const authService = inject(AuthService);
    const router = inject(Router);

    if (authService.temPapelMinimo(papelMinimo)) {
      return true;
    }
    return router.parseUrl('/app/provas');
  };
}

export const adminGuard: CanActivateFn = () => {
  const authService = inject(AuthService);
  const router = inject(Router);

  if (authService.isAdmin()) {
    return true;
  }
  return router.parseUrl('/app/provas');
};
