"""
Plans d'abonnement et facturation.
"""
from django.db import models


class Plan(models.Model):
    """Plan d'abonnement."""
    name = models.CharField('Nom', max_length=100)
    price = models.DecimalField('Prix mensuel (€)', max_digits=10, decimal_places=2, default=0)
    monthly_quota = models.IntegerField('Quota mensuel (contacts)', default=500)
    features = models.JSONField('Fonctionnalités', default=list, blank=True)
    stripe_price_id = models.CharField('Stripe Price ID', max_length=255, blank=True)
    is_active = models.BooleanField('Actif', default=True)

    class Meta:
        verbose_name = 'Plan'
        verbose_name_plural = 'Plans'

    def __str__(self):
        return f'{self.name} ({self.monthly_quota} contacts/mois)'
