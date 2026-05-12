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
    company = Company.objects.select_related('current_plan').filter(user=user).first()
    if not company:
        messages.warning(request, 'Aucune entreprise associée à votre compte. Veuillez contacter le support.')
        return redirect('accounts:login')

    uploads_qs = company.uploads.all()
    processings_qs = company.processings.all()

    total_uploads = uploads_qs.count()
    total_exports = processings_qs.count()
    total_contacts_processed = sum(
        p.rows_after_filter for p in processings_qs.only('rows_after_filter')
    )
    total_valid_phones = sum(
        p.rows_valid_phones for p in processings_qs.only('rows_valid_phones')
    )
    quota_percent = min(100, (company.contacts_used_this_month / company.monthly_quota * 100)
                        if company.monthly_quota else 0)

    context = {
        'user': user,
        'company': company,
        'total_uploads': total_uploads,
        'total_exports': total_exports,
        'total_contacts_processed': total_contacts_processed,
        'total_valid_phones': total_valid_phones,
        'quota_percent': quota_percent,
    }
    return render(request, 'accounts/profile.html', context)
