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

# Configuration du logging pour traçabilité
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# ============ VALIDATION ET SÉCURISATION DES ENTRÉES ============

class Sanitizer:
    """Nettoyage et validation des entrées pour prévenir les injections et erreurs."""
    
    @staticmethod
    def safe_string(value: Any, max_length: int = 10000) -> str:
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
        if value is None:
            return None
        try:
            if isinstance(value, (int, float)):
                return float(value)
            cleaned = str(value).replace(',', '.').strip()
            if cleaned.count('.') > 1:
                parts = cleaned.split('.')
                cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
            return float(cleaned)
        except (ValueError, TypeError, AttributeError):
            return None
    
    @staticmethod
    def safe_list(value: Any, separator: str = ',') -> List[str]:
        if value is None:
            return []
        try:
            items = str(value).split(separator)
            return [item.strip().lower() for item in items if item.strip()]
        except Exception:
            return []

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
            row_hash = hashlib.md5(
                json.dumps(row, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            rule_hash = hashlib.md5(
                json.dumps(rule, sort_keys=True).encode()
            ).hexdigest()[:16]
            return f"{row_hash}_{rule_hash}"
        except Exception:
            return ""
    
    def get(self, key: str) -> Optional[bool]:
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None
    
    def set(self, key: str, value: bool):
        if len(self._cache) >= self._max_size:
            items_to_remove = list(self._cache.keys())[:int(self._max_size * 0.2)]
            for k in items_to_remove:
                del self._cache[k]
        self._cache[key] = value
    
    def get_stats(self) -> Dict:
        total = self._hits + self._misses
        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_ratio': self._hits / total if total > 0 else 0
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
    return Sanitizer.safe_string(val) == Sanitizer.safe_string(target)

@safe_operation
def _not_equals(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(val) != Sanitizer.safe_string(target)

@safe_operation
def _contains(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(target) in Sanitizer.safe_string(val)

@safe_operation
def _not_contains(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(target) not in Sanitizer.safe_string(val)

@safe_operation
def _startswith(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(val).startswith(Sanitizer.safe_string(target))

@safe_operation
def _endswith(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(val).endswith(Sanitizer.safe_string(target))


@safe_operation
def _not_startswith(val: Any, target: Any) -> bool:
    return not Sanitizer.safe_string(val).startswith(Sanitizer.safe_string(target))

@safe_operation
def _is_empty(val: Any, _: Any) -> bool:
    return not Sanitizer.safe_string(val)

@safe_operation
def _not_empty(val: Any, _: Any) -> bool:
    return bool(Sanitizer.safe_string(val))

@safe_operation
def _in_list(val: Any, target: Any) -> bool:
    val_clean = Sanitizer.safe_string(val)
    target_list = Sanitizer.safe_list(target)
    # Pour les préfixes comme "6,7", vérifier si la valeur commence par un des éléments
    for item in target_list:
        if val_clean.startswith(item):
            return True
    return val_clean in target_list

@safe_operation
def _regex(val: Any, target: Any) -> bool:
    try:
        pattern = Sanitizer.safe_string(target)
        if len(pattern) > 1000:
            return False
        return bool(re.search(pattern, Sanitizer.safe_string(val), re.IGNORECASE))
    except re.error:
        return False

@safe_operation
def _greater_than(val: Any, target: Any) -> bool:
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v > t

@safe_operation
def _less_than(val: Any, target: Any) -> bool:
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v < t

@safe_operation
def _greater_or_equal(val: Any, target: Any) -> bool:
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v >= t

@safe_operation
def _less_or_equal(val: Any, target: Any) -> bool:
    v = Sanitizer.safe_numeric(val)
    t = Sanitizer.safe_numeric(target)
    if v is None or t is None:
        return False
    return v <= t

@safe_operation
def _between(val: Any, target: Any) -> bool:
    """Opérateur BETWEEN: target format 'min,max'"""
    try:
        range_str = Sanitizer.safe_string(target)
        if ',' not in range_str:
            return False
        min_val, max_val = range_str.split(',', 1)
        v = Sanitizer.safe_numeric(val)
        min_v = Sanitizer.safe_numeric(min_val)
        max_v = Sanitizer.safe_numeric(max_val)
        if v is None or min_v is None or max_v is None:
            return False
        return min_v <= v <= max_v
    except Exception:
        return False

@safe_operation
def _in_date_range(val: Any, target: Any) -> bool:
    """Vérifie si une date est dans un intervalle: format 'YYYY-MM-DD,YYYY-MM-DD'"""
    try:
        range_str = Sanitizer.safe_string(target)
        if ',' not in range_str:
            return False
        start_str, end_str = range_str.split(',', 1)
        val_date = datetime.fromisoformat(Sanitizer.safe_string(val))
        start_date = datetime.fromisoformat(start_str.strip())
        end_date = datetime.fromisoformat(end_str.strip())
        return start_date <= val_date <= end_date
    except Exception:
        return False

# Opérateurs étendus
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
    'regex': _regex,
    'greater_than': _greater_than,
    'less_than': _less_than,
    'greater_or_equal': _greater_or_equal,
    'less_or_equal': _less_or_equal,
    'between': _between,
    'in_date_range': _in_date_range,
}

# ============ SYSTÈME DE VALIDATION DE TÉLÉPHONE RENFORCÉ ============

class PhoneValidator:
    """Validation téléphonique robuste avec cache."""
    
    _cache = {}
    _max_cache = 5000
    
    @classmethod
    def validate(cls, phone: Any, default_region: str = 'FR') -> Tuple[bool, str]:
        if not phone:
            return False, ''
        
        raw = Sanitizer.safe_string(phone)
        cache_key = f"{raw}_{default_region}"
        
        if cache_key in cls._cache:
            return cls._cache[cache_key]
        
        result = cls._do_validate(raw, default_region)
        
        if len(cls._cache) >= cls._max_cache:
            cls._cache.clear()
        cls._cache[cache_key] = result
        
        return result
    
    @classmethod
    def _do_validate(cls, raw: str, default_region: str) -> Tuple[bool, str]:
        cleaned = re.sub(r'[^\d+]', '', raw)
        
        if not HAS_PHONENUMBERS:
            is_valid = len(cleaned) >= 10 and cleaned.replace('+', '').isdigit()
            return is_valid, raw if is_valid else ''
        
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
        if not HAS_PHONENUMBERS or not phone:
            return None
        try:
            parsed = phonenumbers.parse(Sanitizer.safe_string(phone), default_region)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.region_code_for_number(parsed)
        except NumberParseException:
            pass
        return None

# ============ APPLICATION DES RÈGLES AVEC CACHE ET SUPPORT GROUPE ============

_cache = FilterCache()

def apply_filter_rule(row: Dict[str, Any], rule: Dict) -> bool:
    """Applique une règle simple avec cache et validation renforcée."""
    
    field = rule.get('field')
    operator = rule.get('operator')
    value = rule.get('value')
    
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
        result = op_func(row_val, value if value is not None else '')
        
        if cache_key:
            _cache.set(cache_key, result)
        
        return result
    except Exception as e:
        logger.error(f"Error applying rule {rule}: {e}")
        return False


def is_group_node(node: Dict) -> bool:
    """
    Détermine si un nœud est un groupe (AND/OR).
    Supporte à la fois l'ancien et le nouveau format.
    """
    # Nouveau format avec 'type': 'group'
    if node.get('type') == 'group':
        return True
    # Ancien format: a 'logic' et 'rules' sans 'type' mais avec des règles
    if 'logic' in node and 'rules' in node and node['rules']:
        # Vérifier si les règles sont des dicts (pas des listes simples)
        if node['rules'] and isinstance(node['rules'][0], dict):
            return True
    return False


def apply_filter_group(row: Dict[str, Any], group: Dict) -> bool:
    """
    Applique un groupe de règles (AND/OR) avec support de l'imbrication.
    Supporte à la fois l'ancien format (sans 'type') et le nouveau format (avec 'type': 'group').
    """
    
    # Extraire la logique et les règles
    logic = group.get('logic', 'AND')
    rules = group.get('rules', [])
    
    if not rules:
        return True
    
    # Protection contre les récursions trop profondes
    max_depth = 20
    
    def _evaluate(rules_list, depth=0):
        if depth > max_depth:
            logger.warning("Max recursion depth reached in filter groups")
            return True
        
        results = []
        for item in rules_list:
            # Vérifier si c'est un sous-groupe
            if is_group_node(item):
                # C'est un sous-groupe, évaluation récursive
                sub_logic = item.get('logic', 'AND')
                sub_rules = item.get('rules', [])
                
                if not sub_rules:
                    continue
                
                sub_results = _evaluate(sub_rules, depth + 1)
                results.append(sub_results)
            else:
                # C'est une règle simple
                results.append(apply_filter_rule(row, item))
        
        if not results:
            return True
        
        if logic.upper() == 'OR':
            return any(results)
        return all(results)
    
    try:
        return _evaluate(rules)
    except Exception as e:
        logger.error(f"Error evaluating filter group: {e}")
        return True


def apply_scoring(row: Dict[str, Any], config: List[Dict]) -> int:
    """Calcul de score avec validation des entrées."""
    
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
            
            row_val = row.get(field, '')
            op_func = OPERATORS.get(operator)
            
            if op_func and op_func(row_val, value if value is not None else ''):
                total += points
                
        except Exception as e:
            logger.debug(f"Scoring error: {e}")
            continue
    
    return total


# ============ FONCTION PRINCIPALE AMÉLIORÉE ============

def normalize_filters_config(filters_config: Dict) -> Dict:
    """
    Normalise la configuration des filtres pour supporter à la fois
    l'ancien format (liste plate) et le nouveau format (imbriqué).
    """
    if not filters_config:
        return {'logic': 'AND', 'rules': []}
    
    # Si c'est déjà une configuration valide avec structure imbriquée
    if 'rules' in filters_config and filters_config['rules']:
        # Vérifier si les règles sont déjà au bon format
        first_rule = filters_config['rules'][0] if filters_config['rules'] else None
        if first_rule and (is_group_node(first_rule) or 'field' in first_rule):
            return filters_config
    
    # Convertir l'ancien format (liste plate) vers le nouveau
    old_rules = filters_config.get('rules', [])
    if old_rules and isinstance(old_rules, list):
        new_rules = []
        for rule in old_rules:
            if 'rules' in rule:
                # C'est déjà un groupe, le garder tel quel
                new_rules.append(rule)
            elif 'field' in rule:
                # C'est une règle simple, ajouter 'type'
                new_rules.append({
                    'type': 'rule',
                    'field': rule.get('field'),
                    'operator': rule.get('operator'),
                    'value': rule.get('value', '')
                })
        
        return {
            'logic': filters_config.get('logic', 'AND'),
            
            'rules': new_rules
        }
    
    return filters_config


def filter_and_score_rows(
    rows: List[Dict],
    filters_config: Dict,
    scoring_config: List[Dict],
    min_score: int = 0,
    phone_field: str = 'phone',
    default_region: str = 'FR',
) -> Tuple[List[Dict], int, int]:
    """
    Version ultra-robuste du filtre avec:
    - Support des groupes AND/OR imbriqués
    - Validation des entrées
    - Cache intelligent
    - Protection contre les erreurs
    """
    
    # Validation des entrées
    if not rows:
        return [], 0, 0
    
    if not isinstance(rows, list):
        logger.error("rows must be a list")
        return [], 0, 0
    
    # Normaliser la configuration
    if filters_config:
        filters_config = normalize_filters_config(filters_config)
    
    # Préparation
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
            # Application des filtres (supporte maintenant l'imbrication)
            if filters_config and filters_config.get('rules'):
                if not apply_filter_group(row, filters_config):
                    stats['filtered_out'] += 1
                    continue
            
            # Calcul du score
            score = apply_scoring(row, scoring_config) if scoring_config else 0
            
            if score < min_score:
                stats['score_too_low'] += 1
                continue
            
            # Validation téléphone
            phone_value = row.get(phone_field, '')
            is_valid, normalized = PhoneValidator.validate(phone_value, default_region)
            
            if is_valid and normalized:
                valid_phones += 1
            
            # Enrichissement de la ligne
            enriched_row = {
                **row,
                '_score': score,
                'phone_valid': is_valid,
                'phone_normalized': normalized if is_valid else phone_value,
                '_filter_metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'score': score,
                    'phone_validated': is_valid
                }
            }
            
            filtered.append(enriched_row)
            stats['kept'] += 1
            
        except Exception as e:
            logger.error(f"Error processing row {idx}: {e}")
            stats['errors'] += 1
            continue
    
    # Log des statistiques
    logger.info(f"Filter stats: {dict(stats)}")
    logger.info(f"Cache stats: {_cache.get_stats()}")
    
    rejected = len(rows) - len(filtered) - stats.get('errors', 0)
    
    return filtered, valid_phones, rejected


# ============ FONCTIONS UTILITAIRES SUPPLÉMENTAIRES ============

def reset_cache():
    """Reset le cache de filtrage."""
    global _cache
    _cache = FilterCache()


def get_filter_stats() -> Dict:
    """Retourne les statistiques du filtre."""
    return _cache.get_stats()


def validate_filter_config(filters_config: Dict) -> Tuple[bool, str]:
    """Valide une configuration de filtres avec support imbriqué."""
    
    if not filters_config:
        return True, "Empty config"
    
    required_keys = {'logic', 'rules'}
    if not all(k in filters_config for k in required_keys):
        return False, f"Missing required keys: {required_keys - set(filters_config.keys())}"
    
    if filters_config['logic'] not in ['AND', 'OR']:
        return False, f"Invalid logic: {filters_config['logic']}"
    
    if not isinstance(filters_config['rules'], list):
        return False, "rules must be a list"
    
    def validate_rules(rules_list, depth=0):
        if depth > 20:
            return False, "Le niveau d'imbrication est trop profond"
        
        for rule in rules_list:
            if is_group_node(rule):
                # Valider le sous-groupe
                sub_logic = rule.get('logic')
                if sub_logic not in ['AND', 'OR']:
                    return False, f"Invalid subgroup logic: {sub_logic}"
                
                sub_rules = rule.get('rules', [])
                if not sub_rules:
                    return False, "Empty subgroup"
                
                is_valid, msg = validate_rules(sub_rules, depth + 1)
                if not is_valid:
                    return False, msg
            else:
                # Valider la règle simple
                if not rule.get('field'):
                    return False, "Rule missing field"
                if not rule.get('operator'):
                    return False, "Rule missing operator"
        
        return True, ""
     
    return validate_rules(filters_config['rules'])


# Garder les fonctions existantes pour compatibilité
validate_phone = PhoneValidator.validate
get_phone_country = PhoneValidator.get_country