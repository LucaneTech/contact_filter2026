"""Crée un superuser admin et une entreprise de démo."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User
from apps.companies.models import Company
from apps.billing.models import Plan


class Command(BaseCommand):
    help = 'Crée les données de démo (Plan, Admin, Company)'

    def add_arguments(self, parser):
        parser.add_argument('--email', default='admin@callfilter.local')
        parser.add_argument('--password', default='admin123')
        parser.add_argument('--company-email', default='company@callfilter.local')

    def handle(self, *args, **options):
        # Plan
        plan, _ = Plan.objects.get_or_create(
            name='Starter',
            defaults={'monthly_quota': 500, 'price': 0}
        )
        self.stdout.write(f'Plan: {plan}')

        # Superuser admin
        admin, created = User.objects.get_or_create(
            email=options['email'],
            defaults={
                'is_staff': True,
                'is_superuser': True,
                'is_admin': True,
            }
        )
        if created:
            admin.set_password(options['password'])
            admin.save()
            self.stdout.write(self.style.SUCCESS(f'Admin créé: {admin.email} / {options["password"]}'))
        else:
            self.stdout.write(f'Admin existant: {admin.email}')

        # User entreprise
        company_user, created = User.objects.get_or_create(
            email=options['company_email'],
            defaults={'is_company': True}
        )
        if created:
            company_user.set_password(options['password'])
            company_user.save()

        # Company
        company, created = Company.objects.get_or_create(
            user=company_user,
            defaults={
                'name': 'Centre d\'appel Démo',
                'subscription_status': 'trial',
                'current_plan': plan,
                'monthly_quota': 500,
                'quota_reset_at': timezone.now().date() + timedelta(days=30),
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f'Entreprise créée: {company.name}'))
        self.stdout.write(self.style.SUCCESS(f'Connexion entreprise: {company_user.email} / {options["password"]}'))
