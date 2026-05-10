from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

from apps.companies.models import UploadedFile, Company, ProcessingHistory
from apps.filtering.engine import filter_and_score_rows, reset_cache, get_filter_stats
from apps.exports.services import export_to_file
from contact_filter import settings
from .services import read_file_to_rows, get_standard_row

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_uploaded_file(self, upload_id: int):
    
    
    logger.info(f"Démarrage du traitement du fichier {upload_id}")
    
    try:
        upload = UploadedFile.objects.select_related('company').get(pk=upload_id)
    except UploadedFile.DoesNotExist:
        logger.error(f"Upload {upload_id} introuvable")
        return
    
    # Mise à jour initiale
    upload.status = 'processing'
    upload.progress = 5
    upload.save(update_fields=['status', 'progress'])
    
    try:
        # ========== ÉTAPE 1: LECTURE DU FICHIER ==========
        logger.info(f"Lecture du fichier: {upload.original_name}")
        
        rows, columns = read_file_to_rows(upload)
        upload.rows_original = len(rows)
        upload.progress = 20
        upload.save(update_fields=['rows_original', 'progress'])
        
        if not rows:
            raise ValueError('Aucune donnée trouvée dans le fichier.')
        
        logger.info(f"{len(rows)} lignes lues, {len(columns)} colonnes")
        
        # ========== ÉTAPE 2: MAPPING DES COLONNES ==========
        logger.info("Mapping des colonnes...")
        
        mapping = upload.column_mapping or {}
        standard_rows = []
        mapping_errors = 0
        
        for idx, row in enumerate(rows):
            try:
                std = get_standard_row(row, columns, mapping)
                if std:
                    standard_rows.append(std)
                else:
                    mapping_errors += 1
            except Exception as e:
                logger.warning(f"Erreur mapping ligne {idx}: {e}")
                mapping_errors += 1
                continue
        
        if mapping_errors > 0:
            logger.warning(f"{mapping_errors} lignes ignorées lors du mapping")
        
        if not standard_rows:
            raise ValueError('Aucune ligne valide après mapping.')
        
        logger.info(f"{len(standard_rows)} lignes après mapping")
        
        # ========== ÉTAPE 3: PRÉPARATION DES CONFIGURATIONS ==========
        upload.status = 'filtering'
        upload.progress = 40
        upload.save(update_fields=['status', 'progress'])
        
        logger.info("🔍 Préparation des filtres...")
        
        # Récupérer la configuration des filtres
        filters_config = upload.filters_config or {}
        
        # Récupérer et normaliser la configuration de scoring
        # Le scoring peut être stocké dans un champ JSON séparé ou dans filters_config
        scoring_config_raw = {}
        min_score = 0
        scoring_rules = []
        
        # Essayer de récupérer le scoring_config s'il existe
        if hasattr(upload, 'scoring_config') and upload.scoring_config:
            scoring_config_raw = upload.scoring_config
        # Sinon, chercher dans filters_config (ancien format)
        elif 'scoring' in filters_config:
            scoring_config_raw = filters_config.get('scoring', {})
        
        # Normaliser le scoring
        if isinstance(scoring_config_raw, dict):
            min_score = scoring_config_raw.get('min_score', 0)
            scoring_rules = scoring_config_raw.get('rules', [])
        elif isinstance(scoring_config_raw, list):
            scoring_rules = scoring_config_raw
        
        # Nettoyer filters_config pour ne garder que les filtres
        if 'scoring' in filters_config:
            filters_config = {k: v for k, v in filters_config.items() if k != 'scoring'}
        
        logger.info(f"Configuration: {len(filters_config.get('rules', []))} règles de filtre, "
                   f"{len(scoring_rules)} règles de scoring, score min={min_score}")
        
        # ========== ÉTAPE 4: FILTRAGE ET SCORING ==========
        logger.info("Application des filtres et calcul des scores...")
        
        try:
            alias_map = {v: k for k, v in mapping.items()}
            # Appliquer les filtres avec la fonction principale
            filtered_rows, valid_phones_count, rejected_count = filter_and_score_rows(
                standard_rows,
                filters_config=filters_config,
                scoring_config=scoring_rules,
                min_score=min_score,
                phone_field='tel',  
                default_region='FR',  
                enrich=False,
                alias_map=alias_map,  
            )
            
            # Récupérer les statistiques du cache
            cache_stats = get_filter_stats()
            
        except Exception as e:
            logger.error(f"Erreur lors du filtrage: {e}")
            raise ValueError(f"Erreur de filtrage: {str(e)}")
        
        # Mise à jour des statistiques
        upload.rows_after_filter = len(filtered_rows)
        upload.rows_valid_phones = valid_phones_count
        upload.progress = 80
        upload.save(update_fields=['rows_after_filter', 'rows_valid_phones', 'progress'])
        
        logger.info(f"Résultats: {len(filtered_rows)} lignes gardées, "
                   f"{valid_phones_count} téléphones valides, "
                   f"{rejected_count} lignes rejetées")
        logger.info(f"Cache: hit ratio {cache_stats.get('hit_ratio', 0):.1%}")
        
        # ========== ÉTAPE 5: EXPORT ==========
        logger.info("Export des résultats...")
        upload.status = 'cleaning'
        upload.progress = 85
        upload.save(update_fields=['status', 'progress'])
        
        if filtered_rows:
            result_path, export_format = export_to_file(
                filtered_rows,
                upload.company_id,
                upload.original_name,
            )
        else:
            # Créer un fichier vide avec explication
            result_path, export_format = _create_empty_result_file(
                upload.company_id,
                upload.original_name,
                "Aucun contact ne correspond aux critères de filtrage."
            )
        
        upload.result_file = result_path
        upload.status = 'ready'
        upload.progress = 100
        upload.save(update_fields=['result_file', 'status', 'progress'])
        
        logger.info(f"Export terminé: {result_path} (format: {export_format})")
        
        # ========== ÉTAPE 6: HISTORIQUE ==========
        logger.info("Création de l'historique...")
        
        expires = timezone.now() + timedelta(hours=24)
        
        # Préparer les données pour l'historique
        history_data = {
            'company': upload.company,
            'original_filename': upload.original_name,
            'rows_original': upload.rows_original,
            'rows_after_filter': upload.rows_after_filter,
            'rows_valid_phones': valid_phones_count,
            'filters_applied': {
                'filters': filters_config,
                'scoring': {
                    'rules': scoring_rules,
                    'min_score': min_score
                }
            },
            'expires_at': expires,
            'export_file': upload.result_file,
            'export_format': export_format,
        }
        
        # Ajouter upload_id si le champ existe
        if hasattr(ProcessingHistory, 'upload_id'):
            history_data['upload_id'] = upload.id
        elif hasattr(ProcessingHistory, 'upload'):
            history_data['upload'] = upload
        
        ProcessingHistory.objects.create(**history_data)
        
        # ========== ÉTAPE 7: MISE À JOUR QUOTA ==========
        company = upload.company
        
        # Mettre à jour le quota (gère les différents noms de champs possibles)
        if hasattr(company, 'contacts_used_this_month'):
            company.contacts_used_this_month += upload.rows_original
            company.save(update_fields=['contacts_used_this_month'])
        elif hasattr(company, 'contacts_processed_this_month'):
            company.contacts_processed_this_month = (
                company.contacts_processed_this_month or 0
            ) + upload.rows_original
            company.save(update_fields=['contacts_processed_this_month'])
        
        # ========== FINALISATION ==========
        # Nettoyer le cache
        reset_cache()
        
        logger.info(f"Traitement terminé avec succès pour {upload.original_name}")
        
        # Retourner les statistiques pour Celery
        return {
            'status': 'success',
            'upload_id': upload_id,
            'rows_original': upload.rows_original,
            'rows_filtered': upload.rows_after_filter,
            'valid_phones': valid_phones_count,
            'rejected': rejected_count,
            'result_file': str(upload.result_file) if upload.result_file else None,
            'cache_stats': cache_stats
        }
        
    except ValueError as e:
        # Erreur métier (données invalides, pas de lignes, etc.)
        logger.error(f"Erreur de validation: {e}")
        upload.status = 'failed'
        upload.error_message = str(e)[:500]
        upload.save(update_fields=['status', 'error_message'])
        
        return {
            'status': 'error',
            'upload_id': upload_id,
            'error': str(e),
            'error_type': 'validation_error'
        }
        
    except Exception as e:
        # Erreur inattendue
        logger.exception(f"Erreur inattendue lors du traitement: {e}")
        
        upload.status = 'failed'
        upload.error_message = f"Erreur technique: {str(e)[:500]}"
        upload.save(update_fields=['status', 'error_message'])
        
        # Réessayer si c'est une erreur temporaire et qu'il reste des tentatives
        if self.request.retries < self.max_retries:
            logger.info(f"Nouvelle tentative ({self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)
        
        return {
            'status': 'error',
            'upload_id': upload_id,
            'error': str(e),
            'error_type': 'technical_error'
        }


def _create_empty_result_file(company_id: int, original_name: str, message: str) -> tuple:
    """
    Crée un fichier de résultat vide avec un message explicatif.
    Utilisé quand aucun contact ne passe les filtres.
    """
    import os
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from datetime import datetime
    
    # Nettoyer le nom du fichier
    base_name = os.path.splitext(original_name)[0]
    safe_base_name = "".join(c for c in base_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{safe_base_name}_empty_{timestamp}.txt"
    
    # Créer le contenu
    content = f"# Rapport de filtrage\n"
    content += f"# Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    content += f"# Fichier original: {original_name}\n"
    content += f"# \n"
    content += f"# {message}\n"
    content += f"# \n"
    content += f"# Aucun contact ne correspond aux critères spécifiés.\n"
    content += f"# Essayez d'ajuster vos filtres pour obtenir des résultats.\n"
    
    # Sauvegarder le fichier
    path = f"exports/company_{company_id}/{filename}"
    
    try:
        default_storage.save(path, ContentFile(content.encode('utf-8')))
        logger.info(f"Fichier vide créé: {path}")
        return path, 'txt'
    except Exception as e:
        logger.error(f"Erreur création fichier vide: {e}")
        # Fallback: retourner un chemin factice
        return f"exports/company_{company_id}/empty_result_{timestamp}.txt", 'txt'


# ============ TÂCHE DE NETTOYAGE ============

@shared_task
def cleanup_expired_files():
    """
    Tâche périodique pour nettoyer les fichiers expirés.
    À exécuter via Celery Beat.
    """
    from django.utils import timezone
    from datetime import timedelta
    import os
    
    logger.info("Démarrage du nettoyage des fichiers expirés...")
    
    try:
        # Récupérer les historiques expirés
        expired_histories = ProcessingHistory.objects.filter(
            expires_at__lt=timezone.now()
        )
        
        count = 0
        for history in expired_histories:
            try:
                # Supprimer le fichier exporté
                if history.export_file:
                    # Essayer de supprimer le fichier physique
                    try:
                        from django.core.files.storage import default_storage
                        if default_storage.exists(history.export_file):
                            default_storage.delete(history.export_file)
                            logger.info(f"🗑️ Fichier supprimé: {history.export_file}")
                    except Exception as e:
                        logger.warning(f"Impossible de supprimer le fichier {history.export_file}: {e}")
                
                # Supprimer l'entrée d'historique
                history.delete()
                count += 1
                
            except Exception as e:
                logger.error(f"Erreur lors du nettoyage de l'historique {history.id}: {e}")
                continue
        
        logger.info(f"Nettoyage terminé: {count} fichiers expirés supprimés")
        
        return {
            'status': 'success',
            'deleted_count': count
        }
        
    except Exception as e:
        logger.exception(f"💥 Erreur lors du nettoyage: {e}")
        return {
            'status': 'error',
            'error': str(e)
        }


# ============ FONCTION UTILITAIRE POUR LE DÉBOGAGE ============

def debug_filter_config(upload_id: int):
    """
    Fonction utilitaire pour déboguer la configuration des filtres.
    À utiliser dans le shell Django.
    """
    try:
        upload = UploadedFile.objects.get(pk=upload_id)
        
        print("=" * 60)
        print(f"Fichier: {upload.original_name}")
        print(f"Statut: {upload.status}")
        print("=" * 60)
        
        # Afficher la configuration
        import json
        print("\nConfiguration des filtres:")
        if upload.filters_config:
            print(json.dumps(upload.filters_config, indent=2, ensure_ascii=False))
        else:
            print("  Aucune configuration")
        
        print("\nScoring:")
        if hasattr(upload, 'scoring_config') and upload.scoring_config:
            print(json.dumps(upload.scoring_config, indent=2, ensure_ascii=False))
        else:
            print("  Aucun scoring configuré")
        
        print("\nMapping des colonnes:")
        if upload.column_mapping:
            for key, value in upload.column_mapping.items():
                print(f"  {key} -> {value}")
        else:
            print("  Aucun mapping")
        
        # Valider la configuration
        from apps.filtering.engine import validate_filter_config
        
        if upload.filters_config:
            is_valid, message = validate_filter_config(upload.filters_config)
            print(f"\nValidation: {is_valid}")
            if not is_valid:
                print(f"   Message: {message}")
        
        return upload
        
    except UploadedFile.DoesNotExist:
        print(f"Upload {upload_id} introuvable")
        return None