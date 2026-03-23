"""Tâches Celery Beat périodiques."""
from celery import shared_task
from django.utils import timezone
from django.core.files.storage import default_storage

from apps.companies.models import UploadedFile, ProcessingHistory


@shared_task
def cleanup_expired_files():
    """Supprime les fichiers et enregistrements expirés (quotidien)."""
    now = timezone.now()
    # UploadedFile expirés
    expired_uploads = UploadedFile.objects.filter(expires_at__lt=now, status='expired')
    for u in UploadedFile.objects.filter(expires_at__lt=now):
        if u.file:
            try:
                default_storage.delete(u.file.name)
            except Exception:
                pass
        if u.result_file:
            try:
                default_storage.delete(u.result_file.name)
            except Exception:
                pass
        u.status = 'expired'
        u.save()

    # ProcessingHistory expirés
    for p in ProcessingHistory.objects.filter(expires_at__lt=now):
        if p.export_file:
            try:
                default_storage.delete(p.export_file.name)
            except Exception:
                pass
        p.delete()
