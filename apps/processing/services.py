"""Services de lecture des fichiers uploadés."""
import csv
import io
from typing import List, Dict, Any

from django.core.files.storage import default_storage

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def read_file_to_rows(upload) -> tuple[List[Dict], List[str]]:
    """Lit le fichier et retourne (liste de dicts, liste des colonnes)."""
    path = upload.file.name
    filename = getattr(upload.file, 'name', path).lower()

    if filename.endswith('.csv') or filename.endswith('.txt'):
        with default_storage.open(path, 'rb') as f:
            raw = f.read()
        content = raw.decode('utf-8', errors='ignore') if isinstance(raw, bytes) else raw
        reader = csv.DictReader(io.StringIO(content))
        columns = reader.fieldnames or []
        rows = list(reader)
        return rows, columns

    elif HAS_PANDAS and (filename.endswith('.xlsx') or filename.endswith('.xls')):
        with default_storage.open(path, 'rb') as f:
            df = pd.read_excel(f)
        df = df.fillna('')
        columns = list(df.columns)
        rows = df.to_dict('records')
        rows = [{str(k): v for k, v in r.items()} for r in rows]
        return rows, columns

    return [], []


def get_standard_row(raw: Dict, columns: List[str], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Mappe une ligne brute vers les champs standard. mapping: {source_col: target_field}"""
    result = {}
    for col in columns:
        val = raw.get(col, raw.get(str(col), ''))
        std_field = mapping.get(col) or mapping.get(str(col))
        key = std_field if std_field else col
        result[key] = val
    return result
