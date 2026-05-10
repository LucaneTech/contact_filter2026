# apps/uploads/services.py  (ou apps/companies/services.py selon votre arborescence)

import csv
import io
import re
import logging
from django.core.files.uploadedfile import UploadedFile as DjangoUploadedFile

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

logger = logging.getLogger(__name__)

STANDARD_FIELDS = [
    'prenom', 'nom', 'tel', 'email',
    'addresse', 'code_postal', 'ville', 'pays',
    'age', 'sexe', 'habitation',
]

# Valeurs considérées comme vides (issues de pandas ou de mauvaises saisies)
_EMPTY_STRINGS = {'', 'nan', 'NaT', 'None', 'null', 'undefined', 'NA', 'N/A', '#N/A'}


def _clean_val(val) -> str:
    """Convertit n'importe quelle valeur en str propre, '' si vide/nul."""
    if val is None:
        return ''
    s = str(val).strip()
    return '' if s in _EMPTY_STRINGS else s


# ============ DÉTECTION DE COLONNES ============

def detect_columns(file: DjangoUploadedFile) -> list:
    """Détecte les colonnes du fichier (CSV ou Excel)."""
    if not file:
        return []
    filename = getattr(file, 'name', '').lower()
    try:
        if filename.endswith(('.csv', '.txt')):
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            reader = csv.reader(io.StringIO(content))
            header = next(reader, [])
            return [str(h).strip() for h in header if str(h).strip()]
        elif HAS_PANDAS and filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file, nrows=1)
            file.seek(0)
            return [str(c) for c in df.columns]
    except Exception as e:
        logger.warning(f"detect_columns error: {e}")
    return []


def count_rows(file: DjangoUploadedFile) -> int:
    """Compte le nombre de lignes de données dans le fichier."""
    if not file:
        return 0
    filename = getattr(file, 'name', '').lower()
    try:
        if filename.endswith(('.csv', '.txt')):
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            return max(0, len(content.strip().split('\n')) - 1)
        elif HAS_PANDAS and filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file)
            file.seek(0)
            return len(df)
    except Exception as e:
        logger.warning(f"count_rows error: {e}")
    return 0


# ============ AUTO-MAPPING ============

def auto_column_mapping(columns: list) -> dict:
    """
    Détecte automatiquement le mapping colonne_originale → champ_standard.
    Retourne {colonne_originale: champ_standard}.
    """
    keywords = {
        'tel': [
            'tel', 'phone', 'telephone', 'mobile', 'gsm',
            'numéro', 'numero', 'téléphone', 'cellulaire',
        ],
        'email': ['email', 'mail', 'courriel', 'e-mail', 'mél'],
        'prenom': [
            'prenom', 'prénom', 'first', 'nom2', 'frstname',
            'first_name', 'firstname', 'givenname',
        ],
        'nom': [
            'nom', 'name', 'nom1', 'lastname', 'last_name',
            'surname', 'family', 'familyname',
        ],
        'addresse': [
            'adresse', 'address', 'rue', 'street',
            'adress1', 'adress2', 'addr', 'voie',
        ],
        'code_postal': [
            'cp', 'code postal', 'codepostal', 'zip', 'postcode',
            'postal', 'zipcode', 'code_postal', 'cpostal',
        ],
        'ville': ['ville', 'city', 'localité', 'localite', 'town', 'commune'],
        'pays': ['pays', 'country', 'region', 'région', 'nation'],
        'age': ['age', 'âge', 'years', 'années', 'annees'],
        'sexe': [
            'sexe', 'gender', 'genre', 'sexe1',
            'civilité', 'civilite', 'civ', 'titre',
        ],
        'habitation': [
            'habitation', 'housing', 'logement',
            'habitation1', 'habitation2', 'residence',
        ],
    }

    mapping = {}
    for col in columns:
        col_lower = str(col).strip().lower()
        for std_field, kws in keywords.items():
            if any(kw in col_lower for kw in kws):
                mapping[col] = std_field
                logger.debug(f"Auto-mapping : {col!r} → {std_field!r}")
                break
    return mapping


# ============ LECTURE DU FICHIER ============

def read_file_to_rows(upload) -> tuple:
    """
    Lit un fichier uploadé et retourne (rows, columns).
    rows    : liste de dicts bruts {colonne_originale: valeur_str}
    columns : liste des noms de colonnes originaux
    """
    file = upload.file
    filename = getattr(file, 'name', '').lower()
    rows = []
    columns = []

    try:
        if filename.endswith(('.csv', '.txt')):
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            reader = csv.DictReader(io.StringIO(content))
            columns = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]

        elif HAS_PANDAS and filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(file, dtype=str)
            file.seek(0)
            df = df.fillna('')
            columns = list(df.columns)
            rows = df.to_dict('records')

        else:
            # Fallback CSV
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            reader = csv.DictReader(io.StringIO(content))
            columns = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]

    except Exception as e:
        logger.error(f"Erreur lecture fichier : {e}")
        raise ValueError(f"Impossible de lire le fichier : {e}")

    # Nettoyer toutes les valeurs (None, NaT, nan…)
    cleaned_rows = []
    for row in rows:
        cleaned_row = {k: _clean_val(v) for k, v in row.items()}
        cleaned_rows.append(cleaned_row)

    logger.info(f"Fichier lu : {len(cleaned_rows)} lignes, {len(columns)} colonnes")
    return cleaned_rows, columns


# ============ MAPPING STANDARD ============

def get_standard_row(row: dict, columns: list, mapping: dict = None) -> dict | None:
    """
    Mappe une ligne brute vers un dict de champs standard + champs techniques.

    Stratégie (par ordre de priorité) :
      1. Mapping fourni par l'utilisateur  {col_orig → champ_std}
      2. Auto-mapping par mots-clés
      3. Détection heuristique (téléphone, email, code postal)

    Champs techniques ajoutés :
      _tel_raw   : numéro E164 (+336...)
      _tel_local : numéro en format local (0612...)  ← pour les filtres startswith

    Retourne None si aucun champ utile n'a pu être extrait.
    """
    if not row:
        return None

    mapping = mapping or {}
    standard = {}

    # ── Étape 1 : mapping fourni ──────────────────────────────────────────────
    for original_col, std_field in mapping.items():
        if std_field in STANDARD_FIELDS and original_col in row:
            value = _clean_val(row.get(original_col, ''))
            if value:
                standard[std_field] = value
                logger.debug(f"  Mappé : {std_field!r} ← {original_col!r} = {value[:30]!r}")

    # ── Étape 2 : auto-mapping (si mapping incomplet) ─────────────────────────
    if len(standard) < 3:
        auto_map = auto_column_mapping(columns)
        for original_col, std_field in auto_map.items():
            if std_field not in standard and original_col in row:
                value = _clean_val(row.get(original_col, ''))
                if value:
                    standard[std_field] = value
                    logger.debug(f"  Auto-mappé : {std_field!r} ← {original_col!r}")

    # ── Étape 3 : détection heuristique ──────────────────────────────────────
    for key, raw_value in row.items():
        value_str = _clean_val(raw_value)
        if not value_str:
            continue

        # Téléphone par longueur de chiffres
        if 'tel' not in standard:
            digits = re.sub(r'[^\d]', '', value_str)
            if 9 <= len(digits) <= 15:
                # Éviter de prendre un code postal (5 chiffres) comme téléphone
                if not (len(digits) == 5 and 'code_postal' not in standard):
                    standard['tel'] = digits
                    logger.debug(f"  Tél heuristique : {key!r} = {digits[:20]!r}")

        # Email par présence de @
        if 'email' not in standard and '@' in value_str and '.' in value_str:
            standard['email'] = value_str.lower()
            logger.debug(f"  Email heuristique : {key!r}")

        # Code postal : exactement 5 chiffres
        if 'code_postal' not in standard:
            digits = re.sub(r'[^\d]', '', value_str)
            if len(digits) == 5 and digits.isdigit():
                standard['code_postal'] = digits
                logger.debug(f"  CP heuristique : {key!r} = {digits!r}")

    # ── Étape 4 : nettoyage/normalisation des champs ─────────────────────────

    # Téléphone
    if 'tel' in standard:
        tel_clean = re.sub(r'[^\d+]', '', standard['tel'])
        if tel_clean.startswith('0') and len(tel_clean) == 10:
            tel_e164 = '+33' + tel_clean[1:]
        elif tel_clean.startswith('33') and len(tel_clean) == 11:
            tel_e164 = '+' + tel_clean
        elif tel_clean.startswith('+'):
            tel_e164 = tel_clean
        else:
            tel_e164 = '+' + tel_clean

        standard['tel'] = tel_e164

        # ── Champs techniques pour les filtres ──────────────────────────────
        standard['_tel_raw'] = tel_e164           # '+336XXXXXXXX'

        # Format local (pour filtres "commence par 06", "commence par 07"…)
        # On retire le +33 et on remet le 0
        tel_local = re.sub(r'^\+33', '0', tel_e164)
        # Autres indicatifs : retirer le + pour comparer directement
        if tel_local.startswith('+'):
            tel_local = tel_local[1:]             # garde l'indicatif sans +
        standard['_tel_local'] = tel_local        # '0612345678'

        logger.debug(f"  Tél normalisé : {tel_e164!r} / local : {tel_local!r}")

    # Code postal
    if 'code_postal' in standard:
        cp = re.sub(r'[^\d]', '', standard['code_postal'])
        if len(cp) == 4:
            cp = '0' + cp   # code postal belge/suisse à 4 chiffres
        standard['code_postal'] = cp

    # Email
    if 'email' in standard:
        standard['email'] = standard['email'].lower().strip()

    # Nom / prénom → majuscules
    for field in ('nom', 'prenom'):
        if field in standard:
            standard[field] = standard[field].strip().upper()

    # Ville → title case
    if 'ville' in standard:
        standard['ville'] = standard['ville'].strip().title()

    # ── Étape 5 : supprimer les champs vides ─────────────────────────────────
    standard = {k: v for k, v in standard.items() if v}

    # ── Étape 6 : garantir que toutes les valeurs sont des str ───────────────
    standard = {k: str(v) for k, v in standard.items()}

    # Retourner None si aucun champ utile
    if not standard:
        logger.warning("Aucun champ extrait de cette ligne")
        return None

    return standard


def check_quota(company, file) -> bool:
    """Vérifie si l'entreprise a assez de quota pour traiter ce fichier."""
    return company.quota_remaining >= count_rows(file)