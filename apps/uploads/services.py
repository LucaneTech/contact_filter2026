# apps/companies/services.py

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

STANDARD_FIELDS = ['prenom', 'nom', 'tel', 'email', 'addresse', 'code_postal', 'ville', 'pays', 'age', 'sexe', 'habitation']


def detect_columns(file: DjangoUploadedFile) -> list:
    """Détecte les colonnes du fichier (CSV ou Excel)."""
    if not file:
        return []
    filename = getattr(file, 'name', '').lower()
    try:
        if filename.endswith('.csv') or filename.endswith('.txt'):
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            reader = csv.reader(io.StringIO(content))
            header = next(reader, [])
            return [str(h).strip() for h in header if h]
        elif HAS_PANDAS and (filename.endswith('.xlsx') or filename.endswith('.xls')):
            df = pd.read_excel(file, nrows=1)
            file.seek(0)
            return list(df.columns)
    except Exception:
        pass
    return []


def count_rows(file: DjangoUploadedFile) -> int:
    """Compte le nombre de lignes dans le fichier."""
    if not file:
        return 0
    filename = getattr(file, 'name', '').lower()
    try:
        if filename.endswith('.csv') or filename.endswith('.txt'):
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            return max(0, len(content.strip().split('\n')) - 1)
        elif HAS_PANDAS and (filename.endswith('.xlsx') or filename.endswith('.xls')):
            df = pd.read_excel(file)
            file.seek(0)
            return len(df)
    except Exception:
        pass
    return 0


def auto_column_mapping(columns: list) -> dict:
    """
    Auto-détecte le mapping des colonnes.
    Retourne un dictionnaire: colonne_originale -> champ_standard
    """
    mapping = {}
    keywords = {
        'tel': ['tel', 'phone', 'telephone', 'mobile', 'gsm', 'numéro', 'numero', 'téléphone'],
        'email': ['email', 'mail', 'courriel', 'e-mail'],
        'prenom': ['prenom', 'prénom', 'first', 'nom2', 'frstname', 'first_name', 'firstname'],
        'nom': ['nom', 'name', 'nom1', 'lastname', 'last_name', 'surname'],
        'addresse': ['adresse', 'address', 'rue', 'street', 'adress1', 'adress2', 'addr'],
        'code_postal': ['cp', 'code postal', 'codepostal', 'zip', 'postcode', 'CODE POSTAL', 'postal', 'POSTAL', 'zipcode'],
        'ville': ['ville', 'city', 'localité', 'localite', 'town'],
        'pays': ['pays', 'country', 'region', 'région', 'nation'],
        'age': ['age', 'âge', 'years', 'années'],
        'sexe': ['sexe', 'gender', 'genre', 'sexe1', 'civilité', 'civilite'],
        'habitation': ['habitation', 'housing', 'logement', 'habitation1', 'habitation2'],
    }
    
    for col in columns:
        col_lower = str(col).strip().lower()
        for std, kws in keywords.items():
            if any(kw in col_lower for kw in kws):
                mapping[col] = std
                logger.debug(f"Auto-mapping: {col} -> {std}")
                break
    return mapping


def read_file_to_rows(upload) -> tuple:
    """
    Lit un fichier uploadé et retourne (rows, columns).
    rows: liste de dictionnaires (chaque ligne = {colonne: valeur})
    columns: liste des noms de colonnes
    """
    file = upload.file
    filename = getattr(file, 'name', '').lower()
    rows = []
    columns = []
    
    try:
        if filename.endswith('.csv') or filename.endswith('.txt'):
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            reader = csv.DictReader(io.StringIO(content))
            columns = reader.fieldnames or []
            rows = [dict(row) for row in reader]
            
        elif HAS_PANDAS and (filename.endswith('.xlsx') or filename.endswith('.xls')):
            df = pd.read_excel(file, dtype=str)
            file.seek(0)
            df = df.fillna('')
            columns = list(df.columns)
            rows = df.to_dict('records')
        else:
            # Essayer CSV par défaut
            content = file.read().decode('utf-8', errors='ignore')
            file.seek(0)
            reader = csv.DictReader(io.StringIO(content))
            columns = reader.fieldnames or []
            rows = [dict(row) for row in reader]
            
    except Exception as e:
        logger.error(f"Erreur lecture fichier: {e}")
        raise ValueError(f"Impossible de lire le fichier: {e}")
    
    # Nettoyer les valeurs None
    for row in rows:
        for key in list(row.keys()):
            if row[key] is None:
                row[key] = ''
            else:
                row[key] = str(row[key]).strip()
    
    logger.info(f"✅ Fichier lu: {len(rows)} lignes, {len(columns)} colonnes")
    return rows, columns


def get_standard_row(row: dict, columns: list, mapping: dict = None) -> dict:
    """
    Convertit une ligne brute en ligne standardisée selon le mapping.
    
    Args:
        row: Dictionnaire de la ligne brute {colonne_originale: valeur}
        columns: Liste des colonnes du fichier
        mapping: Dictionnaire de mapping {colonne_originale: champ_standard}
                 Exemple: {'Téléphone': 'tel', 'Code Postal': 'code_postal'}
    
    Returns:
        Dictionnaire standardisé avec les clés de STANDARD_FIELDS
    """
    
    if not row:
        return None
    
    standard = {}
    mapping = mapping or {}
    
    # 1. Appliquer le mapping fourni
    for original_col, std_field in mapping.items():
        if std_field in STANDARD_FIELDS and original_col in row:
            value = row.get(original_col, '')
            if value and str(value).strip():
                standard[std_field] = str(value).strip()
                logger.debug(f"  ✓ Mappé: {std_field} <- {original_col} = {str(value)[:30]}")
    
    # 2. Si mapping incomplet, utiliser l'auto-mapping
    if len(standard) < 3:  # Moins de 3 champs mappés
        auto_map = auto_column_mapping(columns)
        for original_col, std_field in auto_map.items():
            if std_field not in standard and original_col in row:
                value = row.get(original_col, '')
                if value and str(value).strip():
                    standard[std_field] = str(value).strip()
                    logger.debug(f"  → Auto-mappé: {std_field} <- {original_col}")
    
    # 3. Détection supplémentaire par motif
    for key, value in row.items():
        if not value or not str(value).strip():
            continue
            
        value_str = str(value).strip()
        
        # Détection téléphone par motif
        if 'tel' not in standard:
            digits = re.sub(r'[^\d]', '', value_str)
            if len(digits) >= 9 and len(digits) <= 15:
                # Vérifier que ce n'est pas un code postal ou autre
                if not (len(digits) == 5 and 'code_postal' not in standard):
                    standard['tel'] = digits
                    logger.debug(f"  → Téléphone détecté par motif: {key} = {digits[:20]}")
        
        # Détection email par motif
        if 'email' not in standard and '@' in value_str and '.' in value_str:
            standard['email'] = value_str.lower()
            logger.debug(f"  → Email détecté par motif: {key}")
        
        # Détection code postal par motif
        if 'code_postal' not in standard:
            digits = re.sub(r'[^\d]', '', value_str)
            if len(digits) == 5 and digits.isdigit():
                standard['code_postal'] = digits
                logger.debug(f"  → Code postal détecté par motif: {key} = {digits}")
    
    # 4. Nettoyage spécifique
    
    # Nettoyer téléphone
    if 'tel' in standard:
        tel_clean = re.sub(r'[^\d+]', '', standard['tel'])
        # Convertir en format international
        if tel_clean.startswith('0') and len(tel_clean) == 10:
            tel_clean = '+33' + tel_clean[1:]
        elif tel_clean.startswith('33') and len(tel_clean) == 11:
            tel_clean = '+' + tel_clean
        elif not tel_clean.startswith('+') and len(tel_clean) >= 10:
            tel_clean = '+' + tel_clean
        
        standard['tel'] = tel_clean
        logger.debug(f"  → Téléphone nettoyé: {standard['tel'][:20]}")
    
    # Nettoyer code postal
    if 'code_postal' in standard:
        cp_clean = re.sub(r'[^\d]', '', standard['code_postal'])
        if len(cp_clean) == 4 and cp_clean.isdigit():
            cp_clean = '0' + cp_clean
        standard['code_postal'] = cp_clean
        logger.debug(f"  → Code postal: {standard['code_postal']}")
    
    # Nettoyer email
    if 'email' in standard:
        standard['email'] = standard['email'].lower().strip()
    
    # Nettoyer nom/prénom (capitaliser)
    for field in ['nom', 'prenom']:
        if field in standard:
            standard[field] = standard[field].strip().upper()
    
    # Nettoyer ville (capitaliser première lettre)
    if 'ville' in standard:
        standard['ville'] = standard['ville'].strip().title()
    
    # 5. Supprimer les champs vides
    for key in list(standard.keys()):
        if not standard[key] or standard[key] == '':
            del standard[key]
    
    # 6. S'assurer que les valeurs sont des strings
    for key in standard:
        standard[key] = str(standard[key])

    
    # Retourner None si aucun champ utile
    if len(standard) == 0:
        logger.warning("Aucun champ n'a pu être extrait de cette ligne")
        return None
    
    return standard


def check_quota(company, file) -> bool:
    """Vérifie si l'entreprise a assez de quota pour traiter ce fichier."""
    rows = count_rows(file)
    return company.quota_remaining >= rows