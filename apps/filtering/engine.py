import re
from typing import Any, Dict, List, Optional, Tuple, Union, Callable
from functools import lru_cache, wraps
from datetime import datetime, date
import hashlib
import json
import logging
from collections import defaultdict

try:
    import phonenumbers
    from phonenumbers import NumberParseException
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

# Configuration du logging
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class Sanitizer:
    """Nettoyage et validation des entrées pour prévenir les injections et erreurs."""
    
    @staticmethod
    def safe_string(value: Any, max_length: int = 10000) -> str:
        """Convertit et nettoie une valeur en chaîne de caractères."""
        if value is None:
            return ""
        try:
            s = str(value)
            if len(s) > max_length:
                s = s[:max_length]
            return s.strip()
        except Exception:
            return ""
    
    @staticmethod
    def safe_numeric(value: Any) -> Optional[float]:
        """Convertit une valeur en nombre flottant de manière sécurisée."""
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return float(value)
            # Nettoyer la chaîne
            cleaned = str(value).replace(',', '.').strip()
            # Gérer les points multiples (ex: 1.000.50)
            if cleaned.count('.') > 1:
                parts = cleaned.split('.')
                cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
            return float(cleaned)
        except (ValueError, TypeError, AttributeError):
            return None
    
    @staticmethod
    def safe_list(value: Any, separator: str = ',') -> List[str]:
        """Convertit une chaîne séparée en liste d'éléments nettoyés."""
        if value is None:
            return []
        try:
            items = str(value).split(separator)
            return [item.strip().lower() for item in items if item.strip()]
        except Exception:
            return []
    
    @staticmethod
    def safe_date(value: Any) -> Optional[date]:
        """Convertit une valeur en date de manière sécurisée."""
        if value is None:
            return None
        try:
            val_str = str(value).strip()
            # Essayer différents formats
            formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d']
            for fmt in formats:
                try:
                    return datetime.strptime(val_str, fmt).date()
                except ValueError:
                    continue
            # Essayer ISO format
            return date.fromisoformat(val_str)
        except Exception:
            return None

# ============ SYSTÈME DE CACHE POUR PERFORMANCES ============

class FilterCache:
    """Cache intelligent pour éviter les recalculs répétitifs."""
    
    def __init__(self, max_size: int = 10000):
        self._cache = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0
    
    def get_key(self, row: Dict, rule: Dict) -> str:
        """Génère une clé unique pour une règle et une ligne."""
        try:
            # Utiliser seulement les champs pertinents pour le cache
            field = rule.get('field', '')
            row_value = str(row.get(field, ''))
            rule_hash = hashlib.md5(
                json.dumps(rule, sort_keys=True).encode()
            ).hexdigest()[:16]
            return f"{row_value}_{rule_hash}"
        except Exception:
            return ""
    
    def get(self, key: str) -> Optional[bool]:
        """Récupère une valeur du cache."""
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None
    
    def set(self, key: str, value: bool):
        """Stocke une valeur dans le cache."""
        if len(self._cache) >= self._max_size:
            # Supprimer 20% des entrées les plus anciennes
            items_to_remove = list(self._cache.keys())[:int(self._max_size * 0.2)]
            for k in items_to_remove:
                del self._cache[k]
        self._cache[key] = value
    
    def clear(self):
        """Vide le cache."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
    
    def get_stats(self) -> Dict:
        """Retourne les statistiques du cache."""
        total = self._hits + self._misses
        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_ratio': self._hits / total if total > 0 else 0,
            'size': len(self._cache)
        }

# ============ OPÉRATEURS AMÉLIORÉS AVEC PROTECTION ============

def safe_operation(func: Callable) -> Callable:
    """Décorateur pour sécuriser les opérations."""
    @wraps(func)
    def wrapper(val: Any, target: Any) -> bool:
        try:
            return func(val, target)
        except Exception as e:
            logger.debug(f"Operation failed: {func.__name__} - {e}")
            return False
    return wrapper

@safe_operation
def _equals(val: Any, target: Any) -> bool:
    """Égalité stricte après nettoyage."""
    return Sanitizer.safe_string(val).lower() == Sanitizer.safe_string(target).lower()

@safe_operation
def _not_equals(val: Any, target: Any) -> bool:
    """Non égalité."""
    return Sanitizer.safe_string(val).lower() != Sanitizer.safe_string(target).lower()

@safe_operation
def _contains(val: Any, target: Any) -> bool:
    """Contient (insensible à la casse)."""
    return Sanitizer.safe_string(target).lower() in Sanitizer.safe_string(val).lower()

@safe_operation
def _not_contains(val: Any, target: Any) -> bool:
    """Ne contient pas."""
    return Sanitizer.safe_string(target).lower() not in Sanitizer.safe_string(val).lower()

@safe_operation
def _startswith(val: Any, target: Any) -> bool:
    """Commence par."""
    return Sanitizer.safe_string(val).lower().startswith(Sanitizer.safe_string(target).lower())

@safe_operation
def _endswith(val: Any, target: Any) -> bool:
    """Finit par."""
    return Sanitizer.safe_string(val).lower().endswith(Sanitizer.safe_string(target).lower())

@safe_operation
def _not_startswith(val: Any, target: Any) -> bool:
    """Ne commence pas par."""
    return not Sanitizer.safe_string(val).lower().startswith(Sanitizer.safe_string(target).lower())

@safe_operation
def _is_empty(val: Any, _: Any) -> bool:
    """Est vide."""
    return not Sanitizer.safe_string(val)

@safe_operation
def _not_empty(val: Any, _: Any) -> bool:
    """N'est pas vide."""
    return bool(Sanitizer.safe_string(val))

@safe_operation
def _in_list(val: Any, target: Any) -> bool:
    """Dans la liste (support exact et préfixes)."""
    val_clean = Sanitizer.safe_string(val).lower()
    target_list = Sanitizer.safe_list(target)
    
    if not target_list:
        return False
    
    # Vérification exacte
    if val_clean in target_list:
        return True
    
    # Vérification des préfixes (utile pour numéros de téléphone)
    for item in target_list:
        if val_clean.startswith(item):
            return True
    
    return False

@safe_operation
def _not_in_list(val: Any, target: Any) -> bool:
    """Pas dans la liste."""
    return not _in_list(val, target)

@safe_operation
def _regex(val: Any, target: Any) -> bool:
    """Expression régulière."""
    try:
        pattern = Sanitizer.safe_string(target)
        # Protection contre les regex trop longues
        if len(pattern) > 1000:
            return False
        return bool(re.search(pattern, Sanitizer.safe_string(val), re.IGNORECASE))
    except re.error:
        return False

@safe_operation
def _greater_than(val: Any, target: Any) -> bool:
    """Supérieur à (numérique)."""
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v > t

@safe_operation
def _less_than(val: Any, target: Any) -> bool:
    """Inférieur à (numérique)."""
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v < t

@safe_operation
def _greater_or_equal(val: Any, target: Any) -> bool:
    """Supérieur ou égal (numérique)."""
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v >= t

@safe_operation
def _less_or_equal(val: Any, target: Any) -> bool:
    """Inférieur ou égal (numérique)."""
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v <= t

@safe_operation
def _between(val: Any, target: Any) -> bool:
    """Entre deux valeurs numériques (format: 'min,max')."""
    try:
        range_str = Sanitizer.safe_string(target)
        if ',' not in range_str:
            return False
        
        parts = range_str.split(',', 1)
        min_val = Sanitizer.safe_numeric(parts[0])
        max_val = Sanitizer.safe_numeric(parts[1])
        v = Sanitizer.safe_numeric(val)
        
        if v is None or min_val is None or max_val is None:
            return False
        
        return min_val <= v <= max_val
    except Exception:
        return False

@safe_operation
def _in_date_range(val: Any, target: Any) -> bool:
    """Date dans un intervalle (format: 'YYYY-MM-DD,YYYY-MM-DD')."""
    try:
        range_str = Sanitizer.safe_string(target)
        if ',' not in range_str:
            return False
        
        start_str, end_str = range_str.split(',', 1)
        val_str = Sanitizer.safe_string(val).strip()
        start_str = start_str.strip()
        end_str = end_str.strip()
        
        # Optimisation: comparaison lexicographique pour format ISO
        if val_str.count('-') == 2 and start_str.count('-') == 2:
            return start_str <= val_str <= end_str
        
        # Fallback sur parsing complet si format différent
        val_date = Sanitizer.safe_date(val)
        start_date = Sanitizer.safe_date(start_str)
        end_date = Sanitizer.safe_date(end_str)
        
        if val_date and start_date and end_date:
            return start_date <= val_date <= end_date
        
        return False
    except Exception:
        return False

@safe_operation
def _phone_valid(val: Any, _: Any) -> bool:
    """Numéro de téléphone valide."""
    is_valid, _ = PhoneValidator.validate(val)
    return is_valid

@safe_operation
def _phone_country(val: Any, target: Any) -> bool:
    """Pays du numéro de téléphone."""
    country = PhoneValidator.get_country(val)
    return country and country.upper() == Sanitizer.safe_string(target).upper()

# Dictionnaire des opérateurs disponibles
OPERATORS = {
    'equals': _equals,
    'not_equals': _not_equals,
    'contains': _contains,
    'not_contains': _not_contains,
    'startswith': _startswith,
    'endswith': _endswith,
    'not_startswith': _not_startswith,
    'is_empty': _is_empty,
    'not_empty': _not_empty,
    'in_list': _in_list,
    'not_in_list': _not_in_list,
    'regex': _regex,
    'greater_than': _greater_than,
    'less_than': _less_than,
    'greater_or_equal': _greater_or_equal,
    'less_or_equal': _less_or_equal,
    'between': _between,
    'in_date_range': _in_date_range,
    'phone_valid': _phone_valid,
    'phone_country': _phone_country,
}

# Opérateurs qui ne nécessitent pas de valeur
NO_VALUE_OPERATORS = {'is_empty', 'not_empty', 'phone_valid'}

# ============ VALIDATION DE TÉLÉPHONE ============

class PhoneValidator:
    """Validation téléphonique robuste avec cache."""
    
    _cache = {}
    _max_cache = 5000
    
    @classmethod
    def validate(cls, phone: Any, default_region: str = 'FR') -> Tuple[bool, str]:
        """Valide et normalise un numéro de téléphone."""
        if not phone:
            return False, ''
        
        raw = Sanitizer.safe_string(phone)
        cache_key = f"{raw}_{default_region}"
        
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        result = cls._do_validate(raw, default_region)
        
        if len(cls._cache) >= cls._max_cache:
            # Supprimer 50% du cache quand plein
            keys = list(cls._cache.keys())[:cls._max_cache // 2]
            for k in keys:
                del cls._cache[k]
        
        cls._cache[cache_key] = result
        return result
    
    @classmethod
    def _do_validate(cls, raw: str, default_region: str) -> Tuple[bool, str]:
        """Validation interne."""
        cleaned = re.sub(r'[^\d+]', '', raw)
        
        if not HAS_PHONENUMBERS:
            # Validation basique sans librairie
            is_valid = len(cleaned) >= 10 and cleaned.replace('+', '').isdigit()
            return is_valid, cleaned if is_valid else raw
        
        try:
            parsed = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_valid_number(parsed):
                normalized = phonenumbers.format_number(
                    parsed, 
                    phonenumbers.PhoneNumberFormat.E164
                )
                return True, normalized
            return False, raw
        except NumberParseException:
            return False, raw
    
    @classmethod
    def get_country(cls, phone: Any, default_region: str = 'FR') -> Optional[str]:
        """Retourne le code pays d'un numéro."""
        if not HAS_PHONENUMBERS or not phone:
            return None
        try:
            parsed = phonenumbers.parse(Sanitizer.safe_string(phone), default_region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.region_code_for_number(parsed)
        except NumberParseException:
            pass
        return None
    
    @classmethod
    def clear_cache(cls):
        """Vide le cache de validation."""
        cls._cache.clear()

# ============ CACHE GLOBAL ============

_cache = FilterCache()

# ============ APPLICATION DES RÈGLES ============

def apply_filter_rule(row: Dict[str, Any], rule: Dict) -> bool:
    """Applique une règle simple avec cache."""
    
    field = rule.get('field')
    operator = rule.get('operator')
    value = rule.get('value', '')
    
    if not field or not operator:
        return True
    
    # Cache lookup
    cache_key = _cache.get_key(row, rule)
    if cache_key:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached
    
    row_val = row.get(field, '')
    op_func = OPERATORS.get(operator)
    
    if not op_func:
        logger.warning(f"Unknown operator: {operator}")
        return True
    
    try:
        # Les opérateurs sans valeur ignorent le paramètre value
        if operator in NO_VALUE_OPERATORS:
            result = op_func(row_val, '')
        else:
            result = op_func(row_val, value if value is not None else '')
        
        if cache_key:
            _cache.set(cache_key, result)
        
        return result
    except Exception as e:
        logger.error(f"Error applying rule {rule}: {e}")
        return False

def is_group_node(node: Dict) -> bool:
    """Détermine si un nœud est un groupe (AND/OR)."""
    if not isinstance(node, dict):
        return False
    return node.get('type') == 'group' or ('logic' in node and 'rules' in node)

def apply_filter_group(row: Dict[str, Any], group: Dict) -> bool:
    """Applique un groupe de règles (AND/OR) avec support d'imbrication."""
    
    if not group:
        return True
    
    logic = group.get('logic', 'AND').upper()
    rules = group.get('rules', [])
    
    if not rules:
        return True
    
    max_depth = 20
    
    def _evaluate(rules_list, depth=0):
        if depth > max_depth:
            logger.warning("Max recursion depth reached")
            return True
        
        results = []
        for item in rules_list:
            if is_group_node(item):
                # Sous-groupe
                sub_logic = item.get('logic', 'AND').upper()
                sub_rules = item.get('rules', [])
                if sub_rules:
                    sub_result = _evaluate(sub_rules, depth + 1)
                    results.append(sub_result)
            else:
                # Règle simple
                results.append(apply_filter_rule(row, item))
        
        if not results:
            return True
        
        return any(results) if logic == 'OR' else all(results)
    
    try:
        return _evaluate(rules)
    except Exception as e:
        logger.error(f"Error evaluating filter group: {e}")
        return True

def apply_scoring(row: Dict[str, Any], config: List[Dict]) -> int:
    """Calcule le score d'une ligne selon la configuration."""
    
    if not config:
        return 0
    
    total = 0
    for rule in config:
        try:
            field = rule.get('field')
            operator = rule.get('operator')
            value = rule.get('value')
            points = rule.get('points', 0)
            
            if not field or not operator or not points:
                continue
            
            op_func = OPERATORS.get(operator)
            if not op_func:
                continue
            
            if operator in NO_VALUE_OPERATORS:
                matches = op_func(row.get(field, ''), '')
            else:
                matches = op_func(row.get(field, ''), value if value is not None else '')
            
            if matches:
                total += points
                
        except Exception as e:
            logger.debug(f"Scoring error: {e}")
            continue
    
    return total

# ============ NORMALISATION DE CONFIGURATION ============

def normalize_filters_config(filters_config: Dict) -> Dict:
    """Normalise la configuration pour supporter tous les formats."""
    
    if not filters_config:
        return {'logic': 'AND', 'rules': []}
    
    # Si déjà au bon format
    if 'rules' in filters_config and isinstance(filters_config['rules'], list):
        # Vérifier si les règles sont déjà normalisées
        if filters_config['rules']:
            first = filters_config['rules'][0]
            if isinstance(first, dict) and ('type' in first or 'field' in first):
                return {
                    'logic': filters_config.get('logic', 'AND').upper(),
                    'rules': filters_config['rules']
                }
    
    # Conversion depuis l'ancien format
    old_rules = filters_config.get('rules', [])
    new_rules = []
    
    for rule in old_rules:
        if isinstance(rule, dict):
            if 'rules' in rule:
                # C'est un groupe
                new_rules.append({
                    'type': 'group',
                    'logic': rule.get('logic', 'AND').upper(),
                    'rules': rule.get('rules', [])
                })
            elif 'field' in rule:
                # C'est une règle simple
                new_rules.append({
                    'type': 'rule',
                    'field': rule.get('field'),
                    'operator': rule.get('operator'),
                    'value': rule.get('value', '')
                })
    
    return {
        'logic': filters_config.get('logic', 'AND').upper(),
        'rules': new_rules
    }

# ============ FONCTION PRINCIPALE ============

def filter_and_score_rows(
    rows: List[Dict],
    filters_config: Dict,
    scoring_config: Optional[List[Dict]] = None,
    min_score: int = 0,
    phone_field: str = 'phone',
    default_region: str = 'FR',
    enrich: bool = True
) -> Tuple[List[Dict], int, int]:
    
    if not rows:
        return [], 0, 0
    
    if not isinstance(rows, list):
        logger.error("rows must be a list")
        return [], 0, 0
    
    # Normaliser la configuration
    if filters_config:
        filters_config = normalize_filters_config(filters_config)
    
    filtered = []
    valid_phones = 0
    stats = defaultdict(int)
    
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            logger.warning(f"Row {idx} is not a dict, skipping")
            stats['skipped'] += 1
            continue
        
        stats['processed'] += 1
        
        try:
            # Application des filtres
            if filters_config and filters_config.get('rules'):
                if not apply_filter_group(row, filters_config):
                    stats['filtered_out'] += 1
                    continue
            
            # Calcul du score
            score = apply_scoring(row, scoring_config) if scoring_config else 0
            
            if score < min_score:
                stats['score_too_low'] += 1
                continue
            
            # Validation téléphone si enrichissement demandé
            if enrich:
                phone_value = row.get(phone_field, '')
                is_valid, normalized = PhoneValidator.validate(phone_value, default_region)
                
                if is_valid:
                    valid_phones += 1
                
                enriched_row = {
                    **row,
                    '_score': score,
                    '_phone_valid': is_valid,
                    '_phone_normalized': normalized if is_valid else phone_value,
                    '_filter_metadata': {
                        'timestamp': datetime.now().isoformat(),
                        'score': score,
                        'phone_validated': is_valid
                    }
                }
                filtered.append(enriched_row)
            else:
                filtered.append({**row, '_score': score})
            
            stats['kept'] += 1
            
        except Exception as e:
            logger.error(f"Error processing row {idx}: {e}")
            stats['errors'] += 1
            continue
    
    logger.info(f"Filter stats: {dict(stats)}")
    logger.info(f"Cache stats: {_cache.get_stats()}")
    
    rejected = len(rows) - len(filtered) - stats.get('errors', 0)
    
    return filtered, valid_phones, rejected

# ============ UTILITAIRES ============

def reset_cache():
    """Reset tous les caches."""
    global _cache
    _cache.clear()
    PhoneValidator.clear_cache()

def get_filter_stats() -> Dict:
    """Retourne les statistiques des filtres."""
    return _cache.get_stats()

def validate_filter_config(filters_config: Dict) -> Tuple[bool, str]:
    """Valide une configuration de filtres."""
    
    if not filters_config:
        return True, "Configuration vide"
    
    if not isinstance(filters_config, dict):
        return False, "La configuration doit être un dictionnaire"
    
    if 'rules' not in filters_config:
        return False, "Clé 'rules' manquante"
    
    if not isinstance(filters_config['rules'], list):
        return False, "'rules' doit être une liste"
    
    logic = filters_config.get('logic', 'AND').upper()
    if logic not in ['AND', 'OR']:
        return False, f"Logique invalide: {logic}"
    
    def validate_rules(rules_list, depth=0):
        if depth > 20:
            return False, "Profondeur d'imbrication trop grande"
        
        for rule in rules_list:
            if not isinstance(rule, dict):
                return False, "Chaque règle doit être un dictionnaire"
            
            if is_group_node(rule):
                # Valider le sous-groupe
                sub_logic = rule.get('logic', 'AND').upper()
                if sub_logic not in ['AND', 'OR']:
                    return False, f"Logique de sous-groupe invalide: {sub_logic}"
                
                sub_rules = rule.get('rules', [])
                if not isinstance(sub_rules, list):
                    return False, "Les règles du sous-groupe doivent être une liste"
                
                if sub_rules:
                    is_valid, msg = validate_rules(sub_rules, depth + 1)
                    if not is_valid:
                        return False, msg
            else:
                # Valider la règle simple
                if 'field' not in rule:
                    return False, "Règle sans champ"
                if 'operator' not in rule:
                    return False, "Règle sans opérateur"
                
                operator = rule['operator']
                if operator not in OPERATORS:
                    return False, f"Opérateur inconnu: {operator}"
                
                # Vérifier si une valeur est requise
                if operator not in NO_VALUE_OPERATORS:
                    if 'value' not in rule:
                        return False, f"Valeur requise pour l'opérateur {operator}"
        
        return True, ""
    
    return validate_rules(filters_config['rules'])

# Compatibilité
validate_phone = PhoneValidator.validate
get_phone_country = PhoneValidator.get_country