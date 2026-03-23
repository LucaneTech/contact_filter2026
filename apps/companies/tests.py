from django.test import TestCase

from apps.accounts.models import User
from apps.companies.models import Company
from apps.billing.models import Plan


class CompanyModelTest(TestCase):
    def setUp(self):
        plan = Plan.objects.create(name='Starter', monthly_quota=500)
        self.user = User.objects.create_user(email='user@co.com', password='pass')

    def test_quota_remaining(self):
        company = Company.objects.create(user=self.user, name='Co', monthly_quota=100, contacts_used_this_month=30)
        self.assertEqual(company.quota_remaining, 70)
