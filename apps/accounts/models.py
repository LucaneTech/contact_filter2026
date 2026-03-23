"""
Modèle User personnalisé - authentification par email.
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Manager pour User avec email comme identifiant."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('L\'email est obligatoire')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_admin', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser doit avoir is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser doit avoir is_superuser=True.')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    User personnalisé : email comme identifiant, pas de username.
    - is_company : utilisateur lié à une entreprise (centre d'appel)
    - is_admin : administrateur plateforme (accès dashboard admin)
    """
    username = None
    email = models.EmailField('email', unique=True)
    is_company = models.BooleanField('Entreprise', default=False)
    is_admin = models.BooleanField('Admin plateforme', default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return self.email
