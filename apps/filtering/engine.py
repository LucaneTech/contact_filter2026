import re
from typing import Any, Dict, List, Optional

try:
    import phonenumbers
    from phonenumbers import NumberParseException
    HAS_PHONENUMBERS = True
except ImportError:
    HAS_PHONENUMBERS = False

# Opérateurs supportés
OPERATORS = {
    'equals': lambda val, target: str(val).strip().lower() == str(target).strip().lower(),
    'not_equals': lambda val, target: str(val).strip().lower() != str(target).strip().lower(),
    'contains': lambda val, target: str(target).lower() in str(val).lower(),
    'not_contains': lambda val, target: str(target).lower() not in str(val).lower(),
    'startswith': lambda val, target: str(val).strip().lower().startswith(str(target).strip().lower()),
    'endswith': lambda val, target: str(val).strip().lower().endswith(str(target).strip().lower()),
    'is_empty': lambda val, _: not str(val).strip(),
    'not_empty': lambda val, _: bool(str(val).strip()),
    'in_list': lambda val, target: str(val).strip().lower() in [x.strip().lower() for x in str(target).split(',') if x.strip()],
    'regex': lambda val, target: bool(re.search(str(target), str(val), re.IGNORECASE)),
    'greater_than': lambda val, target: _numeric_compare(val, target, lambda a, b: a > b),
    'less_than': lambda val, target: _numeric_compare(val, target, lambda a, b: a < b),
    'greater_or_equal': lambda val, target: _numeric_compare(val, target, lambda a, b: a >= b),
    'less_or_equal': lambda val, target: _numeric_compare(val, target, lambda a, b: a <= b),
}


def _numeric_compare(val: Any, target: Any, op) -> bool:
    try:
        a = float(val) if isinstance(val, (int, float)) else float(str(val).replace(',', '.'))
        b = float(target) if isinstance(target, (int, float)) else float(str(target).replace(',', '.'))
        return op(a, b)
    except (ValueError, TypeError):
        return False


def validate_phone(phone: str, default_region: str = 'FR') -> tuple[bool, str]:
    if not phone or not str(phone).strip():
        return False, ''
    raw = str(phone).strip()
    if not HAS_PHONENUMBERS:
        return len(raw) >= 10 and raw.replace('+', '').replace(' ', '').isdigit(), raw
    try:
        parsed = phonenumbers.parse(raw, default_region)
        if phonenumbers.is_valid_number(parsed):
            return True, phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        return False, raw
    except NumberParseException:
        return False, raw


def get_phone_country(phone: str, default_region: str = 'FR') -> Optional[str]:
    """Détecte le pays via l'indicatif téléphonique."""
    if not HAS_PHONENUMBERS or not phone:
        return None
    try:
        parsed = phonenumbers.parse(str(phone).strip(), default_region)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.region_code_for_number(parsed)
    except NumberParseException:
        pass
    return None


def apply_filter_rule(row: Dict[str, Any], rule: Dict) -> bool:
    """Applique une règle de filtre sur une ligne. Retourne True si la ligne passe."""
    field = rule.get('field')
    operator = rule.get('operator')
    value = rule.get('value')
    if not field or not operator:
        return True
    row_val = row.get(field, '')
    op_func = OPERATORS.get(operator)
    if not op_func:
        return True
    try:
        return op_func(row_val, value if value is not None else '')
    except Exception:
        return False


def apply_filter_group(row: Dict[str, Any], group: Dict) -> bool:
    """Applique un groupe de règles (AND/OR)."""
    logic = group.get('logic', 'AND')
    rules = group.get('rules', [])
    if not rules:
        return True
    results = []
    for r in rules:
        if 'rules' in r:
            results.append(apply_filter_group(row, r))
        else:
            results.append(apply_filter_rule(row, r))
    if logic.upper() == 'OR':
        return any(results)
    return all(results)


def apply_scoring(row: Dict[str, Any], config: List[Dict]) -> int:
    """Calcule le score d'une ligne selon les règles de scoring."""
    total = 0
    for rule in config:
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
    return total


def filter_and_score_rows(
    rows: List[Dict],
    filters_config: Dict,
    scoring_config: List[Dict],
    min_score: int = 0,
    phone_field: str = 'phone',
    default_region: str = 'FR',
) -> tuple[List[Dict], int, int]:
    filtered = []
    valid_phones = 0
    for row in rows:
        if filters_config and not apply_filter_group(row, filters_config):
            continue
        score = apply_scoring(row, scoring_config) if scoring_config else 0
        if score < min_score:
            continue
        row['_score'] = score
        is_valid, normalized = validate_phone(row.get(phone_field, ''), default_region)
        row['phone_valid'] = is_valid
        row['phone_normalized'] = normalized if is_valid else row.get(phone_field, '')
        if is_valid and normalized:
            valid_phones += 1
        filtered.append(row)
    return filtered, valid_phones, len(rows) - len(filtered)
