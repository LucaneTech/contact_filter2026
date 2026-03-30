from django.shortcuts import render, redirect
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .forms import EmailLoginForm
from apps.companies.models import Company

class CustomLoginView(LoginView):
    """Connexion par email."""
    template_name = 'accounts/login.html'
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        from django.urls import reverse
        user = self.request.user
        if user.is_admin or user.is_superuser:
            return reverse('dashboard:admin_dashboard')
        return reverse('dashboard:company_dashboard')


def login_view(request):
    view = CustomLoginView.as_view()
    return view(request)


@login_required
def profile_view(request):
    user = request.user
    company = Company.objects.filter(user=user).first()
    if not company:
        messages.warning(request, 'Aucune entreprise associée à votre compte. Veuillez contacter le support.')
        return redirect('accounts:login')
    context = {
        'user': user,
        'company': company,
    }
    return render(request, 'accounts/profile.html', context)
