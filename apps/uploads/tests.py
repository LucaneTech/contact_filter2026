from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.uploads.services import detect_columns, auto_column_mapping, count_rows, check_quota


class DetectColumnsTest(TestCase):
    def test_csv_columns(self):
        content = "Téléphone,Nom,Email,Ville\n0612345678,Dupont,a@a.com,Paris".encode('utf-8')
        f = SimpleUploadedFile("test.csv", content, content_type="text/csv")
        cols = detect_columns(f)
        self.assertIn('Téléphone', cols)
        self.assertIn('Nom', cols)
        self.assertIn('Email', cols)
        self.assertIn('Ville', cols)

    def test_empty_file(self):
        f = SimpleUploadedFile("empty.csv", b"", content_type="text/csv")
        cols = detect_columns(f)
        self.assertEqual(cols, [])


class AutoColumnMappingTest(TestCase):
    def test_phone_mapping(self):
        mapping = auto_column_mapping(['Téléphone', 'Ville', 'Email'])
        self.assertEqual(mapping.get('Téléphone'), 'phone')
        self.assertEqual(mapping.get('Ville'), 'city')
        self.assertEqual(mapping.get('Email'), 'email')

    def test_postal_code(self):
        mapping = auto_column_mapping(['Code postal', 'CP'])
        self.assertIn('postal_code', mapping.values())


class CountRowsTest(TestCase):
    def test_csv_rows(self):
        content = b"a,b,c\n1,2,3\n4,5,6"
        f = SimpleUploadedFile("test.csv", content, content_type="text/csv")
        self.assertEqual(count_rows(f), 2)


class CheckQuotaTest(TestCase):
    def test_quota_ok(self):
        from apps.accounts.models import User
        from apps.companies.models import Company
        from apps.billing.models import Plan
        plan = Plan.objects.create(name='Test', monthly_quota=100)
        user = User.objects.create_user(email='q@q.com', password='pass')
        company = Company.objects.create(user=user, name='Test', monthly_quota=100)
        content = b"a,b\n1,2\n3,4"
        f = SimpleUploadedFile("small.csv", content, content_type="text/csv")
        self.assertTrue(check_quota(company, f))
