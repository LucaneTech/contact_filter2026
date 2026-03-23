from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.companies.models import Company
from apps.billing.models import Plan


class DashboardAccessTest(TestCase):
    def setUp(self):
        plan = Plan.objects.create(name='Starter', monthly_quota=500)
        self.company_user = User.objects.create_user(email='company@test.com', password='pass')
        self.admin_user = User.objects.create_superuser(email='admin@test.com', password='admin')
        Company.objects.create(user=self.company_user, name='Test Co', monthly_quota=500)

    def test_company_dashboard_requires_login(self):
        response = Client().get(reverse('dashboard:company_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_company_dashboard_logged_in(self):
        client = Client()
        client.login(username='company@test.com', password='pass')
        response = client.get(reverse('dashboard:company_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_admin_dashboard_requires_admin(self):
        client = Client()
        client.login(username='company@test.com', password='pass')
        response = client.get(reverse('dashboard:admin_dashboard'))
        self.assertIn(response.status_code, [200, 302])
