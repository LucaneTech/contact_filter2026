
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
from functools import wraps
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

logger = logging.getLogger(__name__)

# ============ SANITIZER ============

class Sanitizer:
    """Nettoyage et validation des entrées."""

    @staticmethod
    def safe_string(value: Any, max_length: int = 10_000) -> str:
        if value is None:
            return ""
        try:
            s = str(value)
            return s[:max_length].strip()
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
            # Gérer "1.000.50" → "1000.50"
            parts = cleaned.split('.')
            if len(parts) > 2:
                cleaned = ''.join(parts[:-1]) + '.' + parts[-1]
            return float(cleaned)
        except (ValueError, TypeError, AttributeError):
            return None

    @staticmethod
    def safe_list(value: Any, separator: str = ',') -> List[str]:
        if value is None:
            return []
        try:
            return [item.strip().lower() for item in str(value).split(separator) if item.strip()]
        except Exception:
            return []

    @staticmethod
    def safe_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        try:
            val_str = str(value).strip()
            for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y%m%d', '%d-%m-%Y'):
                try:
                    return datetime.strptime(val_str, fmt).date()
                except ValueError:
                    continue
            return date.fromisoformat(val_str)
        except Exception:
            return None


# ============ CACHE ============

class FilterCache:
    """Cache LRU simplifié pour éviter les recalculs."""

    def __init__(self, max_size: int = 10_000):
        self._cache: Dict[str, bool] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    def get_key(self, row: Dict, rule: Dict) -> str:
        try:
            field = rule.get('field', '')
            row_value = str(row.get(field, ''))
            rule_hash = hashlib.md5(
                json.dumps(rule, sort_keys=True, default=str).encode()
            ).hexdigest()[:16]
            return f"{row_value}_{rule_hash}"
        except Exception:
            return ""

    def get(self, key: str) -> Optional[bool]:
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def set(self, key: str, value: bool) -> None:
        if len(self._cache) >= self._max_size:
            # Purger 20 % des entrées les plus anciennes
            to_remove = list(self._cache.keys())[:max(1, self._max_size // 5)]
            for k in to_remove:
                del self._cache[k]
        self._cache[key] = value

    def clear(self) -> None:
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def get_stats(self) -> Dict:
        total = self._hits + self._misses
        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_ratio': self._hits / total if total > 0 else 0,
            'size': len(self._cache),
        }


# ============ DÉCORATEUR DE PROTECTION ============

def safe_operation(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(val: Any, target: Any) -> bool:
        try:
            return func(val, target)
        except Exception as e:
            logger.debug(f"Operation failed [{func.__name__}]: {e}")
            return False
    return wrapper


# ============ OPÉRATEURS ============

@safe_operation
def _equals(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(val).lower() == Sanitizer.safe_string(target).lower()

@safe_operation
def _not_equals(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(val).lower() != Sanitizer.safe_string(target).lower()

@safe_operation
def _contains(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(target).lower() in Sanitizer.safe_string(val).lower()

@safe_operation
def _not_contains(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(target).lower() not in Sanitizer.safe_string(val).lower()

@safe_operation
def _startswith(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(val).lower().startswith(Sanitizer.safe_string(target).lower())

@safe_operation
def _not_startswith(val: Any, target: Any) -> bool:
    return not Sanitizer.safe_string(val).lower().startswith(Sanitizer.safe_string(target).lower())

@safe_operation
def _endswith(val: Any, target: Any) -> bool:
    return Sanitizer.safe_string(val).lower().endswith(Sanitizer.safe_string(target).lower())

@safe_operation
def _not_endswith(val: Any, target: Any) -> bool:
    return not Sanitizer.safe_string(val).lower().endswith(Sanitizer.safe_string(target).lower())

@safe_operation
def _is_empty(val: Any, _: Any) -> bool:
    return not Sanitizer.safe_string(val)

@safe_operation
def _not_empty(val: Any, _: Any) -> bool:
    return bool(Sanitizer.safe_string(val))

@safe_operation
def _in_list(val: Any, target: Any) -> bool:
    """Valeur exactement dans la liste (insensible à la casse)."""
    val_clean = Sanitizer.safe_string(val).lower()
    target_list = Sanitizer.safe_list(target)
    if not target_list:
        return False
    if val_clean in target_list:
        return True
    # Correspondance par préfixe (numéros de téléphone, codes postaux…)
    return any(val_clean.startswith(item) for item in target_list)

@safe_operation
def _not_in_list(val: Any, target: Any) -> bool:
    val_clean = Sanitizer.safe_string(val).lower()
    target_list = Sanitizer.safe_list(target)
    if not target_list:
        return True
    if val_clean in target_list:
        return False
    return not any(val_clean.startswith(item) for item in target_list)

@safe_operation
def _equals_any(val: Any, target: Any) -> bool:
    """Égalité exacte avec l'un des éléments de la liste (pas de préfixe)."""
    val_clean = Sanitizer.safe_string(val).lower()
    return val_clean in Sanitizer.safe_list(target)

@safe_operation
def _contains_any(val: Any, target: Any) -> bool:
    """Contient au moins un des termes de la liste."""
    val_low = Sanitizer.safe_string(val).lower()
    return any(item in val_low for item in Sanitizer.safe_list(target))

@safe_operation
def _regex(val: Any, target: Any) -> bool:
    pattern = Sanitizer.safe_string(target)
    if len(pattern) > 1000:
        return False
    return bool(re.search(pattern, Sanitizer.safe_string(val), re.IGNORECASE))

@safe_operation
def _greater_than(val: Any, target: Any) -> bool:
    v, t = Sanitizer.safe_numeric(val), Sanitizer.safe_numeric(target)
    return v is not None and t is not None and v > t

@safe_operation
def _less_than(val: Any, target: Any) -> bool:
    v, t = Sanitizer.safe_numeric(val), Sanitizer.safe_numeric(target)
    return v is not None and t is not None and v < t

@safe_operation
def _greater_or_equal(val: Any, target: Any) -> bool:
    v, t = Sanitizer.safe_numeric(val), Sanitizer.safe_numeric(target)
    return v is not None and t is not None and v >= t

@safe_operation
def _less_or_equal(val: Any, target: Any) -> bool:
    v, t = Sanitizer.safe_numeric(val), Sanitizer.safe_numeric(target)
    return v is not None and t is not None and v <= t

@safe_operation
def _between(val: Any, target: Any) -> bool:
    """Format target: 'min,max' (inclusif)."""
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

@safe_operation
def _in_date_range(val: Any, target: Any) -> bool:
    """Format target: 'YYYY-MM-DD,YYYY-MM-DD' (inclusif)."""
    range_str = Sanitizer.safe_string(target)
    if ',' not in range_str:
        return False
    start_str, end_str = range_str.split(',', 1)
    val_str = Sanitizer.safe_string(val).strip()
    start_str, end_str = start_str.strip(), end_str.strip()

    # Optimisation ISO : comparaison lexicographique
    if val_str.count('-') == 2 and start_str.count('-') == 2 and end_str.count('-') == 2:
        return start_str <= val_str <= end_str

    val_date = Sanitizer.safe_date(val)
    start_date = Sanitizer.safe_date(start_str)
    end_date = Sanitizer.safe_date(end_str)
    if val_date and start_date and end_date:
        return start_date <= val_date <= end_date
    return False

@safe_operation
def _length_equals(val: Any, target: Any) -> bool:
    n = Sanitizer.safe_numeric(target)
    return n is not None and len(Sanitizer.safe_string(val)) == int(n)

@safe_operation
def _length_gt(val: Any, target: Any) -> bool:
    n = Sanitizer.safe_numeric(target)
    return n is not None and len(Sanitizer.safe_string(val)) > int(n)

@safe_operation
def _length_lt(val: Any, target: Any) -> bool:
    n = Sanitizer.safe_numeric(target)
    return n is not None and len(Sanitizer.safe_string(val)) < int(n)

@safe_operation
def _is_numeric(val: Any, _: Any) -> bool:
    return Sanitizer.safe_numeric(val) is not None

@safe_operation
def _is_email(val: Any, _: Any) -> bool:
    s = Sanitizer.safe_string(val)
    return bool(re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', s))

@safe_operation
def _phone_valid(val: Any, _: Any) -> bool:
    is_valid, _ = PhoneValidator.validate(val)
    return is_valid

@safe_operation
def _not_phone_valid(val: Any, _: Any) -> bool:
    is_valid, _ = PhoneValidator.validate(val)
    return not is_valid

@safe_operation
def _phone_country(val: Any, target: Any) -> bool:
    country = PhoneValidator.get_country(val)
    return bool(country) and country.upper() == Sanitizer.safe_string(target).upper()

@safe_operation
def _phone_prefix(val: Any, target: Any) -> bool:
    """Le numéro (nettoyé) commence par un des préfixes de la liste."""
    cleaned = re.sub(r'[^\d+]', '', Sanitizer.safe_string(val))
    return any(cleaned.startswith(p.strip()) for p in Sanitizer.safe_list(target))


# ============ TABLE DES OPÉRATEURS ============

OPERATORS: Dict[str, Callable] = {
    # Égalité
    'equals': _equals,
    'not_equals': _not_equals,
    'equals_any': _equals_any,
    # Contenu textuel
    'contains': _contains,
    'not_contains': _not_contains,
    'contains_any': _contains_any,
    # Préfixe / suffixe
    'startswith': _startswith,
    'not_startswith': _not_startswith,
    'endswith': _endswith,
    'not_endswith': _not_endswith,
    # Vide / non-vide
    'is_empty': _is_empty,
    'not_empty': _not_empty,
    # Listes
    'in_list': _in_list,
    'not_in_list': _not_in_list,
    # Regex
    'regex': _regex,
    # Numérique
    'greater_than': _greater_than,
    'less_than': _less_than,
    'greater_or_equal': _greater_or_equal,
    'less_or_equal': _less_or_equal,
    'between': _between,
    # Date
    'in_date_range': _in_date_range,
    # Longueur
    'length_equals': _length_equals,
    'length_gt': _length_gt,
    'length_lt': _length_lt,
    # Type
    'is_numeric': _is_numeric,
    'is_email': _is_email,
    # Téléphone
    'phone_valid': _phone_valid,
    'not_phone_valid': _not_phone_valid,
    'phone_country': _phone_country,
    'phone_prefix': _phone_prefix,
}

# Opérateurs ne nécessitant pas de valeur cible
NO_VALUE_OPERATORS = {
    'is_empty', 'not_empty',
    'phone_valid', 'not_phone_valid',
    'is_numeric', 'is_email',
}


# ============ VALIDATION DES NUMÉROS DE TÉLÉPHONE ============

class PhoneValidator:
    """Validation téléphonique avec cache."""

    _cache: Dict[str, Tuple[bool, str]] = {}
    _max_cache = 5_000

    @classmethod
    def validate(cls, phone: Any, default_region: str = 'FR') -> Tuple[bool, str]:
        if not phone:
            return False, ''
        raw = Sanitizer.safe_string(phone)
        if not raw:
            return False, ''
        key = f"{raw}_{default_region}"
        if key in cls._cache:
            return cls._cache[key]
        result = cls._do_validate(raw, default_region)
        if len(cls._cache) >= cls._max_cache:
            # Purger la moitié du cache
            for k in list(cls._cache.keys())[:cls._max_cache // 2]:
                del cls._cache[k]
        cls._cache[key] = result
        return result

    @classmethod
    def _do_validate(cls, raw: str, default_region: str) -> Tuple[bool, str]:
        cleaned = re.sub(r'[^\d+]', '', raw)
        if not HAS_PHONENUMBERS:
            # Validation basique
            digits = cleaned.replace('+', '')
            is_valid = 9 <= len(digits) <= 15 and digits.isdigit()
            return is_valid, cleaned if is_valid else raw
        try:
            parsed = phonenumbers.parse(raw, default_region)
            if phonenumbers.is_valid_number(parsed):
                normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
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

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache.clear()


# ============ CACHE GLOBAL ============

_cache = FilterCache()


# ============ APPLICATION DES RÈGLES ============

def apply_filter_rule(row: Dict[str, Any], rule: Dict, alias_map: Optional[Dict[str, str]] = None) -> bool:
    """
    Applique une règle simple.

    alias_map : {champ_standard -> champ_original} ou l'inverse,
    utilisé pour trouver la valeur dans la ligne si le champ direct n'existe pas.
    """
    field = rule.get('field')
    operator = rule.get('operator')
    value = rule.get('value', '')

    if not field or not operator:
        return True  # Règle incomplète → ne filtre pas

    # Résolution de la valeur du champ
    row_val = _resolve_field(row, field, alias_map)

    op_func = OPERATORS.get(operator)
    if not op_func:
        logger.warning(f"Opérateur inconnu : {operator}")
        return True  # Opérateur inconnu → ne filtre pas

    # Cache
    cache_key = _cache.get_key(row, rule)
    if cache_key:
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

    try:
        if operator in NO_VALUE_OPERATORS:
            result = op_func(row_val, '')
        else:
            result = op_func(row_val, value if value is not None else '')
        if cache_key:
            _cache.set(cache_key, result)
        return result
    except Exception as e:
        logger.error(f"Erreur règle {rule}: {e}")
        return False


def _resolve_field(row: Dict, field: str, alias_map: Optional[Dict[str, str]]) -> Any:
    """Cherche la valeur d'un champ dans la ligne, avec fallback vers les alias."""
    if field in row:
        return row[field]
    if alias_map:
        for alias, original in alias_map.items():
            if alias == field and original in row:
                return row[original]
            if original == field and alias in row:
                return row[alias]
    return ''


def is_group_node(node: Any) -> bool:
    if not isinstance(node, dict):
        return False
    return node.get('type') == 'group' or ('logic' in node and 'rules' in node)


def apply_filter_group(
    row: Dict[str, Any],
    group: Dict,
    alias_map: Optional[Dict[str, str]] = None,
    _depth: int = 0,
) -> bool:
    """
    Applique récursivement un groupe de règles AND/OR.

    CORRECTION CRITIQUE : chaque niveau utilise son propre opérateur logique,
    pas celui du niveau parent.
    """
    if not group or _depth > 20:
        return True

    logic = group.get('logic', 'AND').upper()
    rules = group.get('rules', [])

    if not rules:
        return True

    results: List[bool] = []

    for item in rules:
        if not isinstance(item, dict):
            continue

        if is_group_node(item):
            # ── Sous-groupe : on passe la logique propre au sous-groupe ──
            sub_result = apply_filter_group(row, item, alias_map, _depth + 1)
            results.append(sub_result)

            # Court-circuit : AND → premier False suffit, OR → premier True suffit
            if logic == 'AND' and not sub_result:
                return False
            if logic == 'OR' and sub_result:
                return True
        else:
            # ── Règle simple ──
            rule_result = apply_filter_rule(row, item, alias_map)
            results.append(rule_result)

            if logic == 'AND' and not rule_result:
                return False
            if logic == 'OR' and rule_result:
                return True

    if not results:
        return True

    return all(results) if logic == 'AND' else any(results)


def apply_scoring(
    row: Dict[str, Any],
    config: List[Dict],
    alias_map: Optional[Dict[str, str]] = None,
) -> int:
    """Calcule le score pondéré d'une ligne."""
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

            row_val = _resolve_field(row, field, alias_map)

            if operator in NO_VALUE_OPERATORS:
                matches = op_func(row_val, '')
            else:
                matches = op_func(row_val, value if value is not None else '')

            if matches:
                total += int(points)
        except Exception as e:
            logger.debug(f"Scoring error: {e}")
    return total


# ============ NORMALISATION DE CONFIGURATION ============

def normalize_filters_config(filters_config: Any) -> Dict:
    """
    Normalise récursivement la configuration vers le format canonique :
    { logic: 'AND'|'OR', rules: [ <règle> | <groupe> ] }

    Gère les anciens formats et les formats imbriqués.
    """
    if not filters_config or not isinstance(filters_config, dict):
        return {'logic': 'AND', 'rules': []}

    raw_rules = filters_config.get('rules', [])
    if not isinstance(raw_rules, list):
        return {'logic': 'AND', 'rules': []}

    logic = str(filters_config.get('logic', 'AND')).upper()
    if logic not in ('AND', 'OR'):
        logic = 'AND'

    normalized_rules = [_normalize_rule_or_group(r) for r in raw_rules if isinstance(r, dict)]
    normalized_rules = [r for r in normalized_rules if r]

    return {'logic': logic, 'rules': normalized_rules}


def _normalize_rule_or_group(item: Dict) -> Optional[Dict]:
    """Normalise un item (règle simple ou sous-groupe) de façon récursive."""
    if not isinstance(item, dict):
        return None

    # C'est un groupe
    if is_group_node(item):
        sub_logic = str(item.get('logic', 'AND')).upper()
        if sub_logic not in ('AND', 'OR'):
            sub_logic = 'AND'
        sub_rules = item.get('rules', [])
        if not isinstance(sub_rules, list):
            sub_rules = []
        normalized_sub = [_normalize_rule_or_group(r) for r in sub_rules if isinstance(r, dict)]
        return {
            'type': 'group',
            'logic': sub_logic,
            'rules': [r for r in normalized_sub if r],
        }

    # C'est une règle simple
    if 'field' in item and 'operator' in item:
        return {
            'type': 'rule',
            'field': str(item['field']),
            'operator': str(item['operator']),
            'value': item.get('value', ''),
        }

    return None


# ============ VALIDATION DE CONFIGURATION ============

def validate_filter_config(filters_config: Any) -> Tuple[bool, str]:
    """Valide la configuration de filtres. Retourne (is_valid, message)."""
    if not filters_config:
        return True, "Configuration vide"

    if not isinstance(filters_config, dict):
        return False, "La configuration doit être un dictionnaire"

    if 'rules' not in filters_config:
        return False, "Clé 'rules' manquante"

    if not isinstance(filters_config['rules'], list):
        return False, "'rules' doit être une liste"

    logic = str(filters_config.get('logic', 'AND')).upper()
    if logic not in ('AND', 'OR'):
        return False, f"Logique invalide : {logic}"

    return _validate_rules(filters_config['rules'], depth=0)


def _validate_rules(rules_list: List, depth: int) -> Tuple[bool, str]:
    if depth > 20:
        return False, "Profondeur d'imbrication trop grande (max 20)"

    for rule in rules_list:
        if not isinstance(rule, dict):
            return False, "Chaque règle doit être un dictionnaire"

        if is_group_node(rule):
            sub_logic = str(rule.get('logic', 'AND')).upper()
            if sub_logic not in ('AND', 'OR'):
                return False, f"Logique de sous-groupe invalide : {sub_logic}"
            sub_rules = rule.get('rules', [])
            if not isinstance(sub_rules, list):
                return False, "Les règles du sous-groupe doivent être une liste"
            ok, msg = _validate_rules(sub_rules, depth + 1)
            if not ok:
                return False, msg
        else:
            if 'field' not in rule:
                return False, f"Règle sans champ : {rule}"
            if 'operator' not in rule:
                return False, f"Règle sans opérateur : {rule}"
            operator = rule['operator']
            if operator not in OPERATORS:
                return False, f"Opérateur inconnu : {operator}"
            if operator not in NO_VALUE_OPERATORS and 'value' not in rule:
                return False, f"Valeur manquante pour l'opérateur '{operator}'"

    return True, ""


# ============ FONCTION PRINCIPALE ============

def filter_and_score_rows(
    rows: List[Dict],
    filters_config: Optional[Dict],
    scoring_config: Optional[List[Dict]] = None,
    min_score: int = 0,
    phone_field: str = 'tel',          # CORRIGÉ : 'tel' au lieu de 'phone'
    default_region: str = 'FR',
    enrich: bool = False,
    alias_map: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict], int, int]:
    """
    Filtre et score une liste de lignes.

    Paramètres :
        rows           – liste de dicts (une ligne = un contact)
        filters_config – config de filtres (AND/OR imbriqués)
        scoring_config – liste de règles de scoring avec 'points'
        min_score      – seuil minimum de score pour garder la ligne
        phone_field    – nom du champ téléphone dans les rows
        default_region – région par défaut pour la validation téléphonique
        enrich         – si True, ajoute _score, _phone_valid, etc.
        alias_map      – mapping champ_standard ↔ champ_original (optionnel)

    Retourne : (filtered_rows, nb_valid_phones, nb_rejected)
    """
    if not rows:
        return [], 0, 0

    if not isinstance(rows, list):
        logger.error("rows doit être une liste")
        return [], 0, 0

    # Normaliser la configuration
    normalized_filters = normalize_filters_config(filters_config) if filters_config else None
    has_filters = bool(normalized_filters and normalized_filters.get('rules'))

    filtered: List[Dict] = []
    valid_phones = 0
    stats: Dict[str, int] = defaultdict(int)

    # Timestamp commun pour le batch (évite datetime.now() par ligne)
    batch_ts = datetime.now().isoformat()

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            logger.warning(f"Ligne {idx} ignorée (pas un dict)")
            stats['skipped'] += 1
            continue

        stats['processed'] += 1

        try:
            # ── Filtrage ──
            if has_filters:
                if not apply_filter_group(row, normalized_filters, alias_map):
                    stats['filtered_out'] += 1
                    continue

            # ── Scoring ──
            score = apply_scoring(row, scoring_config, alias_map) if scoring_config else 0

            if score < min_score:
                stats['score_too_low'] += 1
                continue

            # ── Enrichissement ──
            if enrich:
                phone_value = _resolve_field(row, phone_field, alias_map)
                is_valid, normalized_phone = PhoneValidator.validate(phone_value, default_region)
                if is_valid:
                    valid_phones += 1

                enriched = {
                        **row,
                        # '_score': score,
                        # '_phone_valid': is_valid,
                        # '_phone_normalized': normalized_phone if is_valid else phone_value,
                        # '_filter_metadata': {
                        #     'timestamp': batch_ts,
                        #     'score': score,
                        #     'phone_validated': is_valid,
                        # },
                    }
                filtered.append(enriched)
            else:
                filtered.append({**row})

            stats['kept'] += 1

        except Exception as e:
            logger.error(f"Erreur ligne {idx}: {e}")
            stats['errors'] += 1

    logger.info(f"Filtrage terminé – stats: {dict(stats)}")
    logger.debug(f"Cache stats: {_cache.get_stats()}")

    rejected = len(rows) - stats['kept'] - stats.get('errors', 0) - stats.get('skipped', 0)
    return filtered, valid_phones, max(0, rejected)


# ============ UTILITAIRES PUBLICS ============

def reset_cache() -> None:
    """Vide tous les caches."""
    _cache.clear()
    PhoneValidator.clear_cache()


def get_filter_stats() -> Dict:
    """Retourne les statistiques du cache de filtres."""
    return _cache.get_stats()


def list_operators() -> List[Dict]:
    """Retourne la liste des opérateurs disponibles avec métadonnées."""
    return [
        {'key': k, 'needs_value': k not in NO_VALUE_OPERATORS}
        for k in sorted(OPERATORS.keys())
    ]


# Alias de compatibilité
validate_phone = PhoneValidator.validate
get_phone_country = PhoneValidator.get_country