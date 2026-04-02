
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from apps.companies.models import UploadedFile, Company, ProcessingHistory
from apps.filtering.engine import filter_and_score_rows
from apps.exports.services import export_to_file
from .services import read_file_to_rows, get_standard_row


@shared_task(bind=True)
def process_uploaded_file(self, upload_id: int):

    try:
        upload = UploadedFile.objects.get(pk=upload_id)
    except UploadedFile.DoesNotExist:
        return

    upload.status = 'processing'
    upload.progress = 5
    upload.save(update_fields=['status', 'progress'])

    try:
        # 1. Lire le fichier
        rows, columns = read_file_to_rows(upload)
        upload.rows_original = len(rows)
        upload.progress = 20
        upload.save(update_fields=['rows_original', 'progress'])

        if not rows:
            upload.status = 'failed'
            upload.error_message = 'Aucune donnée trouvée dans le fichier.'
            upload.save()
            return

        # 2. Mapper les colonnes
        mapping = upload.column_mapping or {}
        standard_rows = []
        for row in rows:
            std = get_standard_row(row, columns, mapping)
            if std:
                standard_rows.append(std)

        upload.status = 'filtering'
        upload.progress = 40
        upload.save(update_fields=['status', 'progress'])

        # 3. Filtrer, scorer, valider téléphones
        filters = upload.filters_config or {}
        scoring = upload.scoring_config or []
        min_score = 0
        if isinstance(scoring, dict):
            min_score = scoring.get('min_score', 0)
            scoring = scoring.get('rules', [])

        filtered_rows, valid_count, _ = filter_and_score_rows(
            standard_rows,
            filters_config=filters,
            scoring_config=scoring,
            min_score=min_score,
        )

        upload.rows_after_filter = len(filtered_rows)
        upload.rows_valid_phones = valid_count
        upload.progress = 80
        upload.save(update_fields=['rows_after_filter', 'rows_valid_phones', 'progress'])

        # 4. Export
        upload.status = 'cleaning'
        upload.save(update_fields=['status'])

        result_path, fmt = export_to_file(
            filtered_rows,
            upload.company_id,
            upload.original_name,
        )

        upload.result_file = result_path
        upload.status = 'ready'
        upload.progress = 100
        upload.save(update_fields=['result_file', 'status', 'progress'])

        # 5. Historique
        expires = timezone.now() + timedelta(days=15)
        ProcessingHistory.objects.create(
            company=upload.company,
            original_filename=upload.original_name,
            rows_original=upload.rows_original,
            rows_after_filter=upload.rows_after_filter,
            rows_valid_phones=valid_count,
            filters_applied=upload.filters_config,
            expires_at=expires,
            export_file=upload.result_file,
            export_format=fmt,
            upload=upload,
        )

        # 6. Mise à jour quota
        company = upload.company
        company.contacts_used_this_month += upload.rows_original
        company.save(update_fields=['contacts_used_this_month'])

    except Exception as e:
        upload.status = 'failed'
        upload.error_message = str(e)[:500]
        upload.save(update_fields=['status', 'error_message'])
