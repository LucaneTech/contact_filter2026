"""Services d'export CSV/Excel."""
import csv
import io
from pathlib import Path
from typing import List, Dict
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


def export_to_file(
    rows: List[Dict],
    company_id: int,
    base_name: str,
    fmt: str = 'csv',
) -> tuple[str, str]:
    """Exporte les lignes vers un fichier. Retourne (path, format)."""
    base = Path(base_name).stem
    date_str = timezone.now().strftime('%Y%m%d_%H%M')
    dir_path = f'exports/company_{company_id}/{timezone.now().strftime("%Y/%m/%d")}'

    if fmt == 'excel' and HAS_PANDAS:
        filename = f'{dir_path}/{base}_{date_str}.xlsx'
        df = pd.DataFrame(rows)
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)
        default_storage.save(filename, ContentFile(buffer.getvalue()))
        return filename, 'xlsx'

    # CSV par défaut
    filename = f'{dir_path}/{base}_{date_str}.csv'
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=rows[0].keys(), extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    default_storage.save(filename, ContentFile(buffer.getvalue().encode('utf-8-sig')))
    return filename, 'csv'
