from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User


class UserModelTest(TestCase):
    def test_create_user(self):
        user = User.objects.create_user(email='test@example.com', password='testpass123')
        self.assertEqual(user.email, 'test@example.com')
        self.assertFalse(user.is_staff)
        self.assertTrue(user.check_password('testpass123'))

    def test_create_superuser(self):
        user = User.objects.create_superuser(email='admin@example.com', password='admin123')
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.is_admin)

    def test_email_unique(self):
        User.objects.create_user(email='dup@example.com', password='pass')
        with self.assertRaises(Exception):
            User.objects.create_user(email='dup@example.com', password='pass2')


class AuthViewsTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='user@test.com', password='test123')
        self.client = Client()

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_login_with_valid_credentials(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'user@test.com',
            'password': 'test123',
        })
        self.assertEqual(response.status_code, 302)

    def test_login_with_invalid_credentials(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'user@test.com',
            'password': 'wrong',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_password_reset_page(self):
        response = self.client.get(reverse('accounts:password_reset'))
        self.assertEqual(response.status_code, 200)

    def test_password_reset_post(self):
        response = self.client.post(reverse('accounts:password_reset'), {'email': 'user@test.com'})
        self.assertEqual(response.status_code, 302)
