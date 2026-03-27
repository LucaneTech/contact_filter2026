from django.db import models
from django.conf import settings
from django.utils import timezone


def company_upload_path(instance, filename):
    return f'uploads/company_{instance.company_id}/{timezone.now().strftime("%Y/%m/%d")}/{filename}'


def company_result_path(instance, filename):
    return f'results/company_{instance.company_id}/{timezone.now().strftime("%Y/%m/%d")}/{filename}'


def company_export_path(instance, filename):
    return f'exports/company_{instance.company_id}/{timezone.now().strftime("%Y/%m/%d")}/{filename}'


class Company(models.Model):
    """Call center """
    SUBSCRIPTION_CHOICES = [
        ('trial', 'Essai'),
        ('active', 'Actif'),
        ('expired', 'Expiré'),
        ('suspended', 'Suspendu'),
    ]
    name = models.CharField('Nom', max_length=255)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='company'
    )
    subscription_status = models.CharField(
        'Statut abonnement',
        max_length=20,
        choices=SUBSCRIPTION_CHOICES,
        default='trial'
    )
    current_plan = models.ForeignKey(
        'billing.Plan',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='companies'
    )
    monthly_quota = models.IntegerField('Quota mensuel', default=500)
    contacts_used_this_month = models.IntegerField('Contacts utilisés ce mois', default=0)
    quota_reset_at = models.DateField('Prochain renouvellement', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    logo = models.ImageField('Logo', upload_to='company_logos/', null=True, blank=True)

    class Meta:
        verbose_name = 'Entreprise'
        verbose_name_plural = 'Entreprises'

    def __str__(self):
        return self.name

    @property
    def quota_remaining(self):
        return max(0, self.monthly_quota - self.contacts_used_this_month)


class UploadedFile(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'Traitement en cours'),
        ('cleaning', 'Nettoyage téléphonique'),
        ('filtering', 'Application des filtres'),
        ('ready', 'Prêt pour export'),
        ('failed', 'Échec'),
        ('expired', 'Expiré'),
    ]
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='uploads'
    )
    file = models.FileField('Fichier', upload_to=company_upload_path)
    original_name = models.CharField('Nom original', max_length=255)
    status = models.CharField(
        'Statut',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    progress = models.IntegerField('Progression %', default=0)
    columns_detected = models.JSONField('Colonnes détectées', default=list)
    column_mapping = models.JSONField('Mapping colonnes', default=dict)
    filters_config = models.JSONField('Config filtres', default=dict)
    scoring_config = models.JSONField('Config scoring', default=dict)
    result_file = models.FileField(
        'Fichier résultat',
        upload_to=company_result_path,
        null=True,
        blank=True
    )
    rows_original = models.IntegerField('Lignes originales', default=0)
    rows_after_filter = models.IntegerField('Lignes après filtre', default=0)
    rows_valid_phones = models.IntegerField('Numéros valides', default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    celery_task_id = models.CharField(max_length=255, null=True, blank=True)
    error_message = models.TextField('Message d\'erreur', blank=True)

    class Meta:
        verbose_name = 'Fichier uploadé'
        verbose_name_plural = 'Fichiers uploadés'

    def __str__(self):
        return f'{self.original_name} ({self.status})'


class ProcessingHistory(models.Model):
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='processings'
    )
    original_filename = models.CharField('Fichier original', max_length=255)
    rows_original = models.IntegerField('Lignes originales', default=0)
    rows_after_filter = models.IntegerField('Lignes après filtre', default=0)
    rows_valid_phones = models.IntegerField('Numéros valides', default=0)
    filters_applied = models.JSONField('Filtres appliqués', default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    export_file = models.FileField(
        'Fichier export',
        upload_to=company_export_path,
        null=True,
        blank=True
    )
    export_format = models.CharField('Format export', max_length=10, null=True, blank=True)
    upload = models.OneToOneField(
        UploadedFile,
        on_delete=models.CASCADE,
        related_name='processing_history',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Historique traitement'
        verbose_name_plural = 'Historiques traitements'

    def __str__(self):
        return f'{self.original_filename} - {self.created_at:%Y-%m-%d %H:%M}'
