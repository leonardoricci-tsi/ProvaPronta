import { Routes } from '@angular/router';

import { authGuard } from './core/guards/auth.guard';
import { guestGuard } from './core/guards/guest.guard';
import { adminGuard, roleGuard } from './core/guards/role.guard';
import { AppShell } from './layout/app-shell/app-shell';

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/login/login').then((m) => m.Login),
  },
  {
    path: 'registro',
    canActivate: [guestGuard],
    loadComponent: () => import('./features/auth/register/register').then((m) => m.Register),
  },
  {
    path: 'esqueci-senha',
    canActivate: [guestGuard],
    loadComponent: () =>
      import('./features/auth/forgot-password/forgot-password').then((m) => m.ForgotPassword),
  },
  {
    path: 'redefinir-senha',
    loadComponent: () =>
      import('./features/auth/reset-password/reset-password').then((m) => m.ResetPassword),
  },
  {
    path: 'app',
    component: AppShell,
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'provas' },
      {
        path: 'turmas',
        loadComponent: () => import('./features/turmas/turmas').then((m) => m.Turmas),
      },
      {
        path: 'turmas/:id',
        loadComponent: () =>
          import('./features/turmas/turma-detalhe/turma-detalhe').then((m) => m.TurmaDetalhe),
      },
      {
        path: 'provas',
        loadComponent: () => import('./features/provas/provas').then((m) => m.Provas),
      },
      {
        // Antes de 'provas/:id', senão "nova" vira um id.
        path: 'provas/nova',
        loadComponent: () =>
          import('./features/provas/prova-form/prova-form').then((m) => m.ProvaForm),
      },
      {
        path: 'provas/:id/editar',
        loadComponent: () =>
          import('./features/provas/prova-form/prova-form').then((m) => m.ProvaForm),
      },
      {
        path: 'provas/:id',
        loadComponent: () =>
          import('./features/provas/prova-detalhe/prova-detalhe').then((m) => m.ProvaDetalhe),
      },
      {
        // Sem id = o próprio perfil (o componente usa o id do JWT).
        path: 'perfil',
        loadComponent: () => import('./features/profile/profile').then((m) => m.Profile),
      },
      {
        path: 'perfil/:id',
        loadComponent: () => import('./features/profile/profile').then((m) => m.Profile),
      },
      {
        // Planos pagos (atividade 7). Também é pra cá que o Stripe devolve
        // o navegador depois do checkout (?checkout=sucesso|cancelado).
        path: 'planos',
        loadComponent: () => import('./features/planos/planos').then((m) => m.Planos),
      },
      {
        // Plano Escola. O guard só esconde a tela; o 403 é do backend.
        path: 'relatorio',
        canActivate: [roleGuard('coordenador')],
        loadComponent: () =>
          import('./features/coordenacao/relatorio').then((m) => m.Relatorio),
      },
      {
        path: 'admin',
        canActivate: [adminGuard],
        loadComponent: () => import('./features/admin/admin').then((m) => m.Admin),
      },
    ],
  },
  {
    path: '',
    loadComponent: () => import('./features/landing/landing').then((m) => m.Landing),
  },
  { path: '**', redirectTo: '' },
];
