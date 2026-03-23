"""Services pour la détection des colonnes et vérification des quotas."""
import csv
import io
from django.core.files.uploadedfile import UploadedFile as DjangoUploadedFile

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

STANDARD_FIELDS = ['first_name', 'last_name', 'phone', 'email', 'address', 'postal_code', 'city', 'country']


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
    """Compte le nombre de lignes (sans header)."""
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
    """Mapping automatique des colonnes vers les champs standard."""
    mapping = {}
    keywords = {
        'phone': ['tel', 'phone', 'telephone', 'mobile', 'gsm', 'numéro', 'numero'],
        'email': ['email', 'mail', 'courriel'],
        'first_name': ['prenom', 'prénom', 'first', 'nom2'],
        'last_name': ['nom', 'name', 'nom1'],
        'address': ['adresse', 'address', 'rue'],
        'postal_code': ['cp', 'code postal', 'codepostal', 'zip'],
        'city': ['ville', 'city', 'localité'],
        'country': ['pays', 'country'],
    }
    for col in columns:
        col_lower = str(col).strip().lower()
        for std, kws in keywords.items():
            if any(kw in col_lower for kw in kws):
                mapping[col] = std
                break
    return mapping


def check_quota(company, file) -> bool:
    """Vérifie si la company a encore du quota pour ce fichier."""
    rows = count_rows(file)
    return company.quota_remaining >= rows
