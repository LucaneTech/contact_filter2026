"""Décorateurs pour l'accès multi-tenant."""
from functools import wraps
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


def company_required(view_func):
    """Redirige vers le dashboard admin si l'utilisateur n'a pas de company."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not getattr(request, 'company', None):
            if request.user.is_admin or request.user.is_superuser:
                return redirect('dashboard:admin_dashboard')
            from django.contrib import messages
            messages.error(request, 'Aucune entreprise associée à votre compte.')
            return redirect('accounts:profile')
        return view_func(request, *args, **kwargs)
    return _wrapped


def admin_required(view_func):
    """Réservé aux admins plateforme."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not (request.user.is_admin or request.user.is_superuser):
            from django.contrib import messages
            messages.error(request, 'Accès réservé aux administrateurs.')
            return redirect('dashboard:company_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped
