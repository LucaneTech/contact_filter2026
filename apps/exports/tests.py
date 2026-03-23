from django.test import TestCase

from apps.exports.services import export_to_file


class ExportServiceTest(TestCase):
    def test_export_csv_empty_rows(self):
        path, fmt = export_to_file([], company_id=1, base_name='test.csv')
        self.assertEqual(fmt, 'csv')
        self.assertIn('.csv', path)

    def test_export_csv_with_data(self):
        rows = [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]
        path, fmt = export_to_file(rows, company_id=1, base_name='data.csv')
        self.assertEqual(fmt, 'csv')
        self.assertIn('.csv', path)
