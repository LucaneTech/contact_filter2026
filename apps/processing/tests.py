from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User
from apps.companies.models import Company, UploadedFile
from apps.billing.models import Plan
from apps.processing.services import read_file_to_rows, get_standard_row


class ProcessingServicesTest(TestCase):
    def setUp(self):
        plan = Plan.objects.create(name='Test', monthly_quota=500)
        user = User.objects.create_user(email='proc@test.com', password='pass')
        self.company = Company.objects.create(user=user, name='Test Co', monthly_quota=500)

    def test_get_standard_row(self):
        raw = {'Téléphone': '0612345678', 'Ville': 'Paris'}
        columns = ['Téléphone', 'Ville']
        mapping = {'Téléphone': 'phone', 'Ville': 'city'}
        result = get_standard_row(raw, columns, mapping)
        self.assertEqual(result['phone'], '0612345678')
        self.assertEqual(result['city'], 'Paris')
