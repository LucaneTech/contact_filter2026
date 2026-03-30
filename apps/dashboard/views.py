from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.utils import timezone

from apps.companies.models import Company, UploadedFile, ProcessingHistory
from apps.companies.decorators import company_required, admin_required
from apps.billing.models import Plan


@login_required
@company_required
def company_dashboard(request):
    company = request.company
    uploads = company.uploads.select_related().order_by('-created_at')[:20]
    processings = company.processings.select_related().order_by('-created_at')[:15]
    quota_used = company.contacts_used_this_month
    quota_total = company.monthly_quota
    pending = company.uploads.filter(status__in=['pending', 'processing', 'cleaning', 'filtering']).count()
    ready_count = company.uploads.filter(status='ready').count()
    total_valid = sum(p.rows_valid_phones for p in processings[:10]) 
    quota_remaining = max(0, quota_total - quota_used)

    context = {
        'company': company,
        'uploads': uploads,
        'processings': processings,
        'quota_used': quota_used,
        'quota_total': quota_total,
        'quota_percent': min(100, (quota_used / quota_total * 100) if quota_total else 0),
        'quota_remaining': quota_remaining,
        'pending_count': pending,
        'ready_count': ready_count,
        'total_valid': total_valid,
        'quota_reset_at': company.quota_reset_at,
    }
    return render(request, 'dashboard/company_dashboard.html', context)


@login_required
@admin_required
def admin_dashboard(request):
    companies = Company.objects.select_related('user', 'current_plan').order_by('-created_at')
    total_uploads = UploadedFile.objects.count()
    total_contacts = sum(c.contacts_used_this_month for c in Company.objects.all())
    active_companies = companies.filter(subscription_status='active').count()
    trial_companies = companies.filter(subscription_status='trial').count()

    context = {
        'companies': companies,
        'total_uploads': total_uploads,
        'total_contacts': total_contacts,
        'companies_count': companies.count(),
        'active_companies': active_companies,
        'trial_companies': trial_companies,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


@login_required
@company_required
def download_export(request, processing_id):
    
    processing = get_object_or_404(
        ProcessingHistory,
        pk=processing_id,
        company=request.company,
    )
    if not processing.export_file:
        raise Http404('Export non disponible')
    try:
        import os
        f = processing.export_file.open('rb')
        name = os.path.basename(processing.export_file.name) or 'export.csv'
        return FileResponse(f, as_attachment=True, filename=name)
    except Exception:
        raise Http404('Fichier introuvable')
