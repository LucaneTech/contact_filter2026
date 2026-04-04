from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
import json
import logging

from apps.companies.models import UploadedFile
from apps.companies.decorators import company_required
from .forms import UploadFileForm
from .services import detect_columns, check_quota, auto_column_mapping
from apps.processing.tasks import process_uploaded_file
from django.conf import settings

logger = logging.getLogger(__name__)


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
                expires_at=timezone.now() + timedelta(days=settings.UPLOADED_FILE_EXPIRATION_TIME),
                columns_detected=columns,
                column_mapping=mapping,
            )
            uploaded.save()
            
            # Message de succès avec le nom du fichier
            messages.success(request, f'Fichier "{f.name}" uploadé avec succès !')
          
            
            return redirect('uploads:filter_config', upload_id=uploaded.pk)
        else:
            messages.error(request, 'Formulaire invalide. Veuillez réessayer.')
            return redirect('dashboard:company_dashboard')
    
    # GET request 
    last_uploaded_file = UploadedFile.objects.filter(
        company=company
    ).order_by('-uploaded_at').first()
    
    context = {
        'last_uploaded_file': last_uploaded_file,
    }
    return render(request, 'dashboard/company_dashboard.html', context)


def validate_filter_config(config: dict) -> tuple[bool, str]:
    """Valide la configuration des filtres (supporte l'imbrication)."""
    
    if not config:
        return True, "Configuration vide"
    
    logic = config.get('logic', 'AND')
    if logic not in ['AND', 'OR']:
        return False, f"Logic invalide: {logic}"
    
    rules = config.get('rules', [])
    if not rules:
        return True, "Aucune règle"
    
    def validate_rules(rules_list, depth=0):
        if depth > 20:  # Protection contre récursion infinie
            return False, "Profondeur maximale dépassée"
        
        for rule in rules_list:
            # Vérifier si c'est un groupe ou une règle simple
            if 'type' in rule and rule.get('type') == 'group':
                # C'est un groupe
                group_logic = rule.get('logic', 'AND')
                if group_logic not in ['AND', 'OR']:
                    return False, f"Logic de groupe invalide: {group_logic}"
                
                group_rules = rule.get('rules', [])
                if not group_rules:
                    return False, "Groupe vide"
                
                # Valider récursivement les règles du groupe
                is_valid, msg = validate_rules(group_rules, depth + 1)
                if not is_valid:
                    return False, msg
            
            else:
                # C'est une règle simple (format ancien ou nouveau)
                field = rule.get('field')
                operator = rule.get('operator')
                
                if not field or not operator:
                    return False, "Règle incomplète: champ ou opérateur manquant"
                
                # Vérifier les opérateurs supportés
                valid_operators = [
                    'equals', 'not_equals', 'contains', 'not_contains',
                    'startswith', 'not_startswith', 'endswith', 'in_list', 'is_empty', 
                    'not_empty', 'regex', 'greater_than', 'less_than',
                    'greater_or_equal', 'less_or_equal', 'between'
                ]
                
                if operator not in valid_operators:
                    return False, f"Opérateur invalide: {operator}"
                
                # Vérifier la valeur pour certains opérateurs
                if operator not in ['is_empty', 'not_empty']:
                    if 'value' not in rule or not rule.get('value'):
                        return False, f"Valeur manquante pour l'opérateur {operator}"
        
        return True, ""
    
    return validate_rules(rules)


def normalize_filter_config(config: dict) -> dict:
    """Normalise l'ancien format de filtres vers le nouveau format imbriqué."""
    
    if not config:
        return {'logic': 'AND', 'rules': []}
    
    # Si c'est déjà le nouveau format avec structure imbriquée
    if 'rules' in config and any('type' in rule for rule in config.get('rules', [])):
        return config
    
    # Convertir l'ancien format (liste plate de règles)
    old_rules = config.get('rules', [])
    if old_rules and isinstance(old_rules, list):
        # Convertir chaque règle en nouveau format
        new_rules = []
        for rule in old_rules:
            if 'rules' in rule:
                # C'est déjà un groupe
                new_rules.append(rule)
            else:
                # C'est une règle simple
                new_rules.append({
                    'type': 'rule',
                    'field': rule.get('field'),
                    'operator': rule.get('operator'),
                    'value': rule.get('value', '')
                })
        
        return {
            'logic': config.get('logic', 'AND'),
            'rules': new_rules
        }
    
    return config


@login_required
@company_required
def filter_config_view(request, upload_id):
    """Configuration des filtres dynamiques avec support des groupes AND/OR imbriqués."""
    
    upload = get_object_or_404(UploadedFile, pk=upload_id, company=request.company)
    
    if upload.status not in ('pending', 'failed'):
        messages.info(request, 'Ce fichier est déjà en cours ou traité.')
        return redirect('dashboard:company_dashboard')

    columns = upload.columns_detected or []
    mapping = upload.column_mapping or {}

    # Construction des champs disponibles pour le filtrage
    filter_fields = []
    for col in columns:
        std = mapping.get(col)
        key = std if std else col
        label = f"{col} ({std})" if std and std != col else col
        if not any(f[0] == key for f in filter_fields):
            filter_fields.append((key, label))

    if request.method == 'POST':
        # Récupération de la nouvelle structure de filtres
        filters_config_json = request.POST.get('filters_config', '{}')
        logic = request.POST.get('logic', 'AND')
        
        try:
            # Essayer de parser le nouveau format d'abord
            if filters_config_json and filters_config_json != '{}':
                filters_config = json.loads(filters_config_json)
            else:
                # Fallback à l'ancien format pour compatibilité
                rules_json = request.POST.get('rules', '[]')
                rules = json.loads(rules_json) if rules_json else []
                filters_config = {'logic': logic, 'rules': rules}
            
            # Normaliser la configuration
            filters_config = normalize_filter_config(filters_config)
            
            # Valider la configuration
            is_valid, error_msg = validate_filter_config(filters_config)
            
            if not is_valid:
                messages.error(request, f'Configuration invalide: {error_msg}')
                # Re-rendre le formulaire avec l'erreur
                context = {
                    'upload': upload,
                    'columns': columns,
                    'filter_fields': filter_fields,
                    'filters_config': json.dumps(filters_config),
                    'error_message': error_msg,
                }
                return render(request, 'uploads/filter_config.html', context)
            
            # Sauvegarder la configuration
            upload.filters_config = filters_config
            upload.save()
            
            # Lancer le traitement
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
                messages.error(request, f'Erreur lors du lancement: {e}')
            
            return redirect('dashboard:company_dashboard')
            
        except json.JSONDecodeError as e:
            messages.error(request, f'Erreur de format JSON: {e}')
            logger.error(f"JSON decode error: {e}")
        except Exception as e:
            messages.error(request, f'Erreur: {e}')
            logger.error(f"Filter config error: {e}")
    
    # GET: Récupérer la configuration existante
    existing_config = upload.filters_config or {'logic': 'AND', 'rules': []}
    existing_config = normalize_filter_config(existing_config)
    
    # Ajouter les types aux règles simples si nécessaire
    for rule in existing_config.get('rules', []):
        if 'rules' not in rule and 'type' not in rule:
            rule['type'] = 'rule'
    
    context = {
        'upload': upload,
        'columns': columns,
        'filter_fields': filter_fields,
        'filters_config': json.dumps(existing_config, default=str),
        'error_message': None,
    }
    
    return render(request, 'uploads/filter_config.html', context)


@login_required
@company_required
@require_http_methods(['GET'])
def upload_status_view(request, upload_id):
    upload = get_object_or_404(UploadedFile, pk=upload_id, company=request.company)
    
    # Retourner aussi la configuration pour debug
    return JsonResponse({
        'status': upload.status,
        'progress': upload.progress,
        'rows_original': upload.rows_original,
        'rows_after_filter': upload.rows_after_filter,
        'rows_valid_phones': upload.rows_valid_phones,
        'error_message': upload.error_message or '',
        'filters_config': upload.filters_config,  # Pour debug
    })


# @login_required
# @company_required
# def test_filters_view(request, upload_id):
#     """View pour tester les filtres sur un échantillon avant traitement."""
    
#     upload = get_object_or_404(UploadedFile, pk=upload_id, company=request.company)
    
#     if request.method == 'POST':
#         try:
#             data = json.loads(request.body)
#             filters_config = data.get('filters_config', {})
            
#             # Normaliser et valider
#             filters_config = normalize_filter_config(filters_config)
#             is_valid, error_msg = validate_filter_config(filters_config)
            
#             if not is_valid:
#                 return JsonResponse({
#                     'valid': False,
#                     'error': error_msg
#                 }, status=400)
            
#             # Ici, vous pouvez charger un échantillon du fichier et tester les filtres
#             # Retourner le nombre de correspondances attendues
            
#             return JsonResponse({
#                 'valid': True,
#                 'message': 'Configuration valide',
#                 'estimated_matches': 0,  # À implémenter
#             })
            
#         except json.JSONDecodeError:
#             return JsonResponse({
#                 'valid': False,
#                 'error': 'JSON invalide'
#             }, status=400)
    
#     return JsonResponse({'error': 'Méthode non supportée'}, status=405)