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
    base = Path(base_name).stem
    date_str = timezone.now().strftime('%Y%m%d_%H%M')
    dir_path = f'exports/company_{company_id}/{timezone.now().strftime("%Y/%m/%d")}'

    # Export Excel
    if fmt == 'excel' and HAS_PANDAS:
        filename = f'{dir_path}/{base}_{date_str}.xlsx'
        df = pd.DataFrame(rows)
        buffer = io.BytesIO()
        df.to_excel(buffer, index=False, engine='openpyxl')
        buffer.seek(0)
        default_storage.save(filename, ContentFile(buffer.getvalue()))
        return filename, 'xlsx'

    # Export TXT
    if fmt == 'txt':
        filename = f'{dir_path}/{base}_{date_str}.txt'
        buffer = io.StringIO()
        if rows:
            # headers = rows[0].keys() if rows else []
            headers = rows[0].keys()
            buffer.write('\t'.join(headers) + '\n')
            
            #writer csv with tab delimiter
            for row in rows:
                values = [str(row.get(key, '')) for key in headers]
                buffer.write('\t'.join(values) + '\n')
        
        default_storage.save(filename, ContentFile(buffer.getvalue().encode('utf-8-sig')))
        return filename, 'txt'

    # Export CSV par défaut
    filename = f'{dir_path}/{base}_{date_str}.csv'
    buffer = io.StringIO()
    if rows:
        writer = csv.DictWriter(buffer, fieldnames=rows[0].keys(), extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    default_storage.save(filename, ContentFile(buffer.getvalue().encode('utf-8-sig')))
    return filename, 'csv'