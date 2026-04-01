from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta

from apps.companies.models import UploadedFile
from apps.companies.decorators import company_required
from .forms import UploadFileForm
from .services import detect_columns, check_quota, auto_column_mapping
from apps.processing.tasks import process_uploaded_file
from django.conf import settings

@login_required
@company_required
def upload_view(request):
    company = request.company
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            f = request.FILES['file']
            if not check_quota(company, f):
                messages.error(request, 'Quota mensuel dépassé. Veuillez upgrader votre plan.')
                return redirect('dashboard:company_dashboard')
            columns = detect_columns(f)
            mapping = auto_column_mapping(columns)
            uploaded = UploadedFile(
                company=company,
                file=f,
                original_name=f.name,
                expires_at=timezone.now() + timedelta(days=15),
                columns_detected=columns,
                column_mapping=mapping,
            )
            uploaded.save()
            return redirect('uploads:filter_config', upload_id=uploaded.pk)
    return redirect('dashboard:company_dashboard')


@login_required
@company_required
def filter_config_view(request, upload_id):
    """Configuration des filtres dynamiques avant traitement."""
    upload = get_object_or_404(UploadedFile, pk=upload_id, company=request.company)
    if upload.status not in ('pending', 'failed'):
        messages.info(request, 'Ce fichier est déjà en cours ou traité.')
        return redirect('dashboard:company_dashboard')

    columns = upload.columns_detected or []
    mapping = upload.column_mapping or {}

    filter_fields = []
    for col in columns:
        std = mapping.get(col)
        key = std if std else col
        label = f"{col} ({std})" if std and std != col else col
        if not any(f[0] == key for f in filter_fields):
            filter_fields.append((key, label))

    if request.method == 'POST':
        import json
        rules_json = request.POST.get('rules', '[]')
        logic = request.POST.get('logic', 'AND')
        try:
            rules = json.loads(rules_json) if rules_json else []
        except json.JSONDecodeError:
            rules = []
        upload.filters_config = {'logic': logic, 'rules': rules}
        upload.save()
        try:
            if settings.CELERY_BROKER_URL and 'redis' in settings.CELERY_BROKER_URL:
                process_uploaded_file.delay(upload.pk)
                messages.success(request, f'Traitement lancé pour "{upload.original_name}".')
                messages.info(request, 'Le traitement peut prendre quelques minutes. Vous recevrez une notification une fois terminé.')
            else:
                process_uploaded_file(upload.pk)
                messages.success(request, f'Fichier "{upload.original_name}" traité.')
        except Exception as e:
            upload.status = 'failed'
            upload.error_message = str(e)
            upload.save()
            messages.error(request, f'Erreur : {e}')
        return redirect('dashboard:company_dashboard')

    context = {
        'upload': upload,
        'columns': columns,
        'filter_fields': filter_fields,
    }
    return render(request, 'uploads/filter_config.html', context)


@login_required
@company_required
@require_http_methods(['GET'])
def upload_status_view(request, upload_id):
    upload = get_object_or_404(UploadedFile, pk=upload_id, company=request.company)
    return JsonResponse({
        'status': upload.status,
        'progress': upload.progress,
        'rows_original': upload.rows_original,
        'rows_after_filter': upload.rows_after_filter,
        'rows_valid_phones': upload.rows_valid_phones,
        'error_message': upload.error_message or '',
    })
