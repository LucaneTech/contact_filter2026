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
    """
    Télécharge l'export dans le format demandé.
    Formats supportés: csv (par défaut), excel, txt
    Utilisation: /export/123/?format=excel
    """
    # Récupérer le format demandé
    format_choice = request.GET.get('format', 'csv').lower()
    
    # Valider le format
    valid_formats = ['csv', 'excel', 'txt']
    if format_choice not in valid_formats:
        format_choice = 'csv'
    
    # Récupérer l'historique de traitement
    processing = get_object_or_404(
        ProcessingHistory,
        pk=processing_id,
        company=request.company,
    )
    
    # Vérifier que l'export existe
    if not processing.export_file:
        raise Http404('Export non disponible')
    
    try:
        # Si le format demandé est le même que l'original, servir directement
        original_format = getattr(processing, 'export_format', 'csv')
        
        if format_choice == original_format:
            # Servir le fichier original
            f = processing.export_file.open('rb')
            name = os.path.basename(processing.export_file.name) or f'export.{original_format}'
            return FileResponse(f, as_attachment=True, filename=name)
        
        # Format différent - re-générer le fichier
        # Récupérer les données à partir du fichier original
        rows = _get_export_data(processing)
        
        if not rows:
            raise Http404('Aucune donnée à exporter')
        
        # Générer le nouveau format
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
