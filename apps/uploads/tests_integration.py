"""Tests d'intégration : flux upload -> filtres -> traitement."""
from datetime import timedelta

from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.accounts.models import User
from apps.companies.models import Company, UploadedFile
from apps.billing.models import Plan


class UploadFilterProcessFlowTest(TestCase):
    """Test du flux complet : upload, config filtres, traitement."""

    def setUp(self):
        plan = Plan.objects.create(name='Starter', monthly_quota=500)
        self.user = User.objects.create_user(email='flow@test.com', password='pass')
        self.company = Company.objects.create(user=self.user, name='Flow Co', monthly_quota=500)
        self.client = Client()
        self.client.login(username='flow@test.com', password='pass')

    def test_upload_redirects_to_filter_config(self):
        content = "Téléphone,Nom,Ville\n0612345678,Dupont,Paris".encode('utf-8')
        f = SimpleUploadedFile("test.csv", content, content_type="text/csv")
        response = self.client.post(reverse('uploads:upload'), {'file': f})
        self.assertEqual(response.status_code, 302)
        self.assertIn('/uploads/', response.url)
        self.assertEqual(UploadedFile.objects.count(), 1)

    def test_filter_config_page_loads(self):
        upload = UploadedFile.objects.create(
            company=self.company,
            file=SimpleUploadedFile("x.csv", b"a,b\n1,2", content_type="text/csv"),
            original_name="x.csv",
            expires_at=timezone.now() + timedelta(days=15),
            columns_detected=['a', 'b'],
            column_mapping={'a': 'x', 'b': 'y'},
        )
        response = self.client.get(reverse('uploads:filter_config', args=[upload.pk]))
        self.assertEqual(response.status_code, 200)
