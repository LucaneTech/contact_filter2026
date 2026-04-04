import logging
from celery import shared_task
from django.utils import timezone
from django.core.files.storage import default_storage

from apps.companies.models import UploadedFile, ProcessingHistory

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_files():
    """
    delete expired uploaded files and processing history records, along with their associated files on disk.
    """
    now = timezone.now()
    
    # 1. Supprimer les fichiers uploadés expirés
    for upload in UploadedFile.objects.filter(expires_at__lt=now):
        try:
            # Supprimer les fichiers physiques
            if upload.file:
                default_storage.delete(upload.file.name)
            if upload.result_file:
                default_storage.delete(upload.result_file.name)
            
            # Supprimer l'enregistrement en base
            upload.delete()
            logger.info(f"Supprimé: {upload.original_name}")
            
        except Exception as e:
            logger.error(f"Erreur suppression upload {upload.id}: {e}")
    
    # 2. Supprimer l'historique expiré
    for history in ProcessingHistory.objects.filter(expires_at__lt=now):
        try:
            # Supprimer le fichier d'export
            if history.export_file:
                default_storage.delete(history.export_file.name)
            
            # Supprimer l'enregistrement
            history.delete()
            logger.info(f"Supprimé: {history.id}")
        except Exception as e:
            logger.error(f"Erreur suppression history {history.id}: {e}")
    
    logger.info("Nettoyage des fichiers expirés terminé")