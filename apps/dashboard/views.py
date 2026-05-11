from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.utils import timezone
from django.contrib import messages
from django.db.models import Q
from django.core.files.storage import default_storage

from apps.companies.models import Company, UploadedFile, ProcessingHistory
from apps.companies.decorators import company_required, admin_required
from apps.billing.models import Plan
from apps.accounts.models import User

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
    total_contacts = Company.objects.values_list('contacts_used_this_month', flat=True)
    active_companies = companies.filter(subscription_status='active').count()
    trial_companies = companies.filter(subscription_status='trial').count()
    recent_uploads = UploadedFile.objects.select_related('company').order_by('-created_at')[:8]
    plans = Plan.objects.prefetch_related('companies').order_by('price')

    # Ajouter quota_percent à chaque company
    for c in companies:
        c.quota_percent = min(100, (c.contacts_used_this_month / c.monthly_quota * 100) if c.monthly_quota else 0)

    context = {
        'companies': companies[:8],
        'total_uploads': total_uploads,
        'total_contacts': sum(total_contacts),
        'companies_count': companies.count(),
        'active_companies': active_companies,
        'trial_companies': trial_companies,
        'recent_uploads': recent_uploads,
        'plans': plans,
    }
    return render(request, 'dashboard/admin_dashboard.html', context)


# ── ENTREPRISES ────────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_companies(request):
    qs = Company.objects.select_related('user', 'current_plan').order_by('-created_at')
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(user__email__icontains=q))
    if status:
        qs = qs.filter(subscription_status=status)
    for c in qs:
        c.quota_percent = min(100, (c.contacts_used_this_month / c.monthly_quota * 100) if c.monthly_quota else 0)
    return render(request, 'dashboard/admin_companies.html', {'companies': qs})


@login_required
@admin_required
def admin_company_edit(request, pk):
    company = get_object_or_404(Company, pk=pk)
    plans = Plan.objects.filter(is_active=True).order_by('price')

    if request.method == 'POST':
        company.name = request.POST.get('name', company.name).strip()
        company.subscription_status = request.POST.get('subscription_status', company.subscription_status)
        company.monthly_quota = int(request.POST.get('monthly_quota', company.monthly_quota) or 0)
        company.contacts_used_this_month = int(request.POST.get('contacts_used_this_month', 0) or 0)
        plan_id = request.POST.get('current_plan')
        company.current_plan = Plan.objects.filter(pk=plan_id).first() if plan_id else None
        reset_at = request.POST.get('quota_reset_at')
        company.quota_reset_at = reset_at if reset_at else None
        company.save()
        messages.success(request, f'Entreprise « {company.name} » mise à jour.')
        return redirect('dashboard:admin_companies')

    company.quota_percent = min(100, (company.contacts_used_this_month / company.monthly_quota * 100) if company.monthly_quota else 0)
    return render(request, 'dashboard/admin_company_edit.html', {'company': company, 'plans': plans})


@login_required
@admin_required
def admin_company_delete(request, pk):
    if request.method == 'POST':
        company = get_object_or_404(Company, pk=pk)
        name = company.name
        company.delete()
        messages.success(request, f'Entreprise « {name} » supprimée.')
    return redirect('dashboard:admin_companies')


# ── UTILISATEURS ───────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_users(request):
    qs = User.objects.order_by('-date_joined')
    q = request.GET.get('q', '').strip()
    role = request.GET.get('role', '')
    if q:
        qs = qs.filter(email__icontains=q)
    if role == 'admin':
        qs = qs.filter(is_admin=True)
    elif role == 'company':
        qs = qs.filter(is_company=True)
    elif role == 'staff':
        qs = qs.filter(is_staff=True)
    return render(request, 'dashboard/admin_users.html', {'users': qs})


@login_required
@admin_required
def admin_user_form(request, pk=None):
    user_obj = get_object_or_404(User, pk=pk) if pk else None
    role_fields = [
        ('is_admin',   'Administrateur plateforme', 'amber', getattr(user_obj, 'is_admin',   False)),
        ('is_company', 'Compte entreprise',         'blue',  getattr(user_obj, 'is_company', False)),
        ('is_staff',   'Staff Django',              'slate', getattr(user_obj, 'is_staff',   False)),
    ]

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        is_active  = 'is_active'  in request.POST
        is_admin   = 'is_admin'   in request.POST
        is_company = 'is_company' in request.POST
        is_staff   = 'is_staff'   in request.POST

        if user_obj:
            user_obj.email = email
            user_obj.is_active  = is_active
            user_obj.is_admin   = is_admin
            user_obj.is_company = is_company
            user_obj.is_staff   = is_staff
            if password:
                user_obj.set_password(password)
            user_obj.save()
            messages.success(request, f'Utilisateur {email} mis à jour.')
        else:
            if User.objects.filter(email=email).exists():
                messages.error(request, f"L'adresse {email} est déjà utilisée.")
                return render(request, 'dashboard/admin_user_form.html',
                              {'user_obj': None, 'role_fields': role_fields})
            user_obj = User.objects.create_user(
                email=email, password=password,
                is_active=is_active, is_admin=is_admin,
                is_company=is_company, is_staff=is_staff,
            )
            messages.success(request, f'Utilisateur {email} créé.')
        return redirect('dashboard:admin_users')

    return render(request, 'dashboard/admin_user_form.html',
                  {'user_obj': user_obj, 'role_fields': role_fields})


@login_required
@admin_required
def admin_user_delete(request, pk):
    if request.method == 'POST':
        user_obj = get_object_or_404(User, pk=pk)
        if user_obj.is_superuser:
            messages.error(request, 'Impossible de supprimer un superuser.')
        else:
            email = user_obj.email
            user_obj.delete()
            messages.success(request, f'Utilisateur {email} supprimé.')
    return redirect('dashboard:admin_users')


# ── PLANS ──────────────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_plans(request):
    plans = Plan.objects.prefetch_related('companies').order_by('price')
    return render(request, 'dashboard/admin_plans.html', {'plans': plans})


@login_required
@admin_required
def admin_plan_form(request, pk=None):
    plan = get_object_or_404(Plan, pk=pk) if pk else None

    if request.method == 'POST':
        name          = request.POST.get('name', '').strip()
        price         = request.POST.get('price', '0') or '0'
        monthly_quota = int(request.POST.get('monthly_quota', '500') or 500)
        stripe_id     = request.POST.get('stripe_price_id', '').strip()
        is_active     = 'is_active' in request.POST
        features_raw  = request.POST.get('features', '')
        features      = [f.strip() for f in features_raw.splitlines() if f.strip()]

        if plan:
            plan.name           = name
            plan.price          = price
            plan.monthly_quota  = monthly_quota
            plan.stripe_price_id = stripe_id
            plan.is_active      = is_active
            plan.features       = features
            plan.save()
            messages.success(request, f'Plan « {name} » mis à jour.')
        else:
            plan = Plan.objects.create(
                name=name, price=price, monthly_quota=monthly_quota,
                stripe_price_id=stripe_id, is_active=is_active, features=features,
            )
            messages.success(request, f'Plan « {name} » créé.')
        return redirect('dashboard:admin_plans')

    return render(request, 'dashboard/admin_plan_form.html', {'plan': plan})


@login_required
@admin_required
def admin_plan_delete(request, pk):
    if request.method == 'POST':
        plan = get_object_or_404(Plan, pk=pk)
        name = plan.name
        plan.delete()
        messages.success(request, f'Plan « {name} » supprimé.')
    return redirect('dashboard:admin_plans')


# ── TRAITEMENTS ────────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_uploads(request):
    qs = UploadedFile.objects.select_related('company').order_by('-created_at')
    q = request.GET.get('q', '').strip()
    status = request.GET.get('status', '')
    if q:
        qs = qs.filter(original_name__icontains=q)
    if status:
        qs = qs.filter(status=status)
    return render(request, 'dashboard/admin_uploads.html', {'uploads': qs})


@login_required
@admin_required
def admin_upload_delete(request, pk):
    if request.method == 'POST':
        upload = get_object_or_404(UploadedFile, pk=pk)
        for field in (upload.file, upload.result_file):
            if field and field.name and default_storage.exists(field.name):
                default_storage.delete(field.name)
        upload.delete()
        messages.success(request, 'Traitement supprimé.')
    return redirect('dashboard:admin_uploads')


# ── HISTORIQUES ────────────────────────────────────────────────────────────────

@login_required
@admin_required
def admin_histories(request):
    qs = ProcessingHistory.objects.select_related('company').order_by('-created_at')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(original_filename__icontains=q)
    return render(request, 'dashboard/admin_histories.html',
                  {'histories': qs, 'now': timezone.now()})


@login_required
@admin_required
def admin_history_delete(request, pk):
    if request.method == 'POST':
        history = get_object_or_404(ProcessingHistory, pk=pk)
        if history.export_file and history.export_file.name and default_storage.exists(history.export_file.name):
            default_storage.delete(history.export_file.name)
        history.delete()
        messages.success(request, 'Historique supprimé.')
    return redirect('dashboard:admin_histories')


#companies details view
@login_required
@admin_required
def company_detail(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    uploads = company.uploads.select_related().order_by('-created_at')[:20]
    processings = company.processings.select_related().order_by('-created_at')[:15]
    pourcent_quota_left = min(100, (company.contacts_used_this_month / company.monthly_quota * 100) if company.monthly_quota else 0)
    context = {
        'company': company,
        'uploads': uploads,
        'processings': processings,
        'pourcent_quota_left': pourcent_quota_left,
    }
    return render(request, 'dashboard/company_detail.html', context)



import os
import io
import csv
from django.http import Http404, FileResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.companies.decorators import company_required
from apps.exports.services import export_to_file
from apps.companies.models import ProcessingHistory


@login_required
@company_required
def download_export(request, processing_id):
    
    # Get the requested format from query parameters (default to 'csv')
    format_choice = request.GET.get('format', 'csv').lower()
    
    # Validate the requested format
    valid_formats = ['csv', 'excel', 'txt']
    if format_choice not in valid_formats:
        format_choice = 'csv'
    
    # Get the processing history object and ensure it belongs to the current company
    processing = get_object_or_404(
        ProcessingHistory,
        pk=processing_id,
        company=request.company,
    )
    
    # Check if the export file exists
    if not processing.export_file:
        raise Http404('Export non disponible')
    
    try:
        # If the requested format is the same as the original, serve the original file
        original_format = getattr(processing, 'export_format', 'csv')
        
        if format_choice == original_format:
            # Serve the original file
            f = processing.export_file.open('rb')
            name = os.path.basename(processing.export_file.name) or f'export.{original_format}'
            return FileResponse(f, as_attachment=True, filename=name)
        
        # Otherwise, read the original file, convert it to the new format, and serve the new file
        rows = _get_export_data(processing)
        
        if not rows:
            raise Http404('Aucune donnée à exporter')
        
        # Manage conversion and caching
        new_path, new_format = export_to_file(
            rows,
            request.company.id,
            processing.original_filename,
            fmt=format_choice
        )
        
        # Servir le nouveau fichier
        if default_storage.exists(new_path):
            f = default_storage.open(new_path, 'rb')
            name = os.path.basename(new_path)
            
            # Optionnel: Supprimer le fichier temporaire après téléchargement
            # default_storage.delete(new_path)
            
            return FileResponse(f, as_attachment=True, filename=name)
        else:
            raise Http404('Fichier généré introuvable')
            
    except Exception as e:
        raise Http404(f'Erreur lors du téléchargement: {str(e)}')


def _get_export_data(processing):
    """
    Récupère les données d'export à partir du fichier existant.
    Retourne une liste de dictionnaires.
    """
    try:
        # Déterminer le format original
        original_format = getattr(processing, 'export_format', 'csv')
        
        # Essayer d'utiliser pandas pour une lecture simplifiée
        try:
            import pandas as pd
            
            file_path = processing.export_file.path
            
            if original_format == 'csv':
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            elif original_format == 'excel':
                df = pd.read_excel(file_path, engine='openpyxl')
            elif original_format == 'txt':
                df = pd.read_csv(file_path, sep='\t', encoding='utf-8-sig')
            else:
                # Fallback CSV
                df = pd.read_csv(file_path, encoding='utf-8-sig')
            
            # Convertir en liste de dictionnaires
            return df.to_dict('records')
            
        except ImportError:
            # Fallback sans pandas
            return _read_file_without_pandas(processing, original_format)
            
    except Exception as e:
        # Log l'erreur (optionnel)
        print(f"Erreur lecture fichier: {e}")
        return []


def _read_file_without_pandas(processing, file_format):
    """
    Lit un fichier sans pandas (fallback).
    """
    rows = []
    
    try:
        # Ouvrir le fichier en mode texte
        with processing.export_file.open('r', encoding='utf-8-sig') as f:
            if file_format == 'csv':
                reader = csv.DictReader(f)
                rows = list(reader)
                
            elif file_format == 'txt':
                # Deviner le séparateur (tabulation ou virgule)
                sample = f.readline()
                f.seek(0)
                delimiter = '\t' if '\t' in sample else ','
                reader = csv.DictReader(f, delimiter=delimiter)
                rows = list(reader)
                
            else:
                # Essayer CSV par défaut
                f.seek(0)
                reader = csv.DictReader(f)
                rows = list(reader)
                
    except Exception as e:
        print(f"Erreur lecture fichier sans pandas: {e}")
        
    return rows
