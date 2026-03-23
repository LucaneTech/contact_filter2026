"""Test d'intégration du traitement complet."""
from datetime import timedelta

from django.test import TestCase
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.utils import timezone

from apps.accounts.models import User
from apps.companies.models import Company, UploadedFile, ProcessingHistory
from apps.billing.models import Plan
from apps.processing.tasks import process_uploaded_file


class FullProcessingTest(TestCase):
    """Test du traitement complet d'un fichier."""

    def setUp(self):
        plan = Plan.objects.create(name='Starter', monthly_quota=500)
        user = User.objects.create_user(email='proc@test.com', password='pass')
        self.company = Company.objects.create(user=user, name='Test Co', monthly_quota=500)

    def test_process_csv_file(self):
        # Créer un fichier CSV dans le storage
        path = f'uploads/company_{self.company.pk}/test/contacts.csv'
        content = "Téléphone,Nom,Ville\n0612345678,Dupont,Paris\n0698765432,Martin,Lyon".encode('utf-8')
        default_storage.save(path, ContentFile(content))

        upload = UploadedFile.objects.create(
            company=self.company,
            file=path,
            original_name='contacts.csv',
            expires_at=timezone.now() + timedelta(days=15),
            columns_detected=['Téléphone', 'Nom', 'Ville'],
            column_mapping={'Téléphone': 'phone', 'Nom': 'last_name', 'Ville': 'city'},
            filters_config={'logic': 'AND', 'rules': []},
        )

        process_uploaded_file(upload.pk)

        upload.refresh_from_db()
        self.assertEqual(upload.status, 'ready', f"Expected ready, got {upload.status}: {upload.error_message}")
        self.assertEqual(upload.rows_original, 2)
        self.assertEqual(upload.rows_after_filter, 2)
        self.assertGreaterEqual(upload.rows_valid_phones, 1)
        self.assertEqual(upload.progress, 100)

        self.assertEqual(ProcessingHistory.objects.filter(company=self.company).count(), 1)
        self.company.refresh_from_db()
        self.assertEqual(self.company.contacts_used_this_month, 2)
