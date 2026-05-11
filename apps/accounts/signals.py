from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender='accounts.User')
def handle_user_roles(sender, instance, created, **kwargs):
    _sync_company(instance, created)
    _sync_admin(instance, created)


def _sync_company(user, created):
    from apps.companies.models import Company

    if not user.is_company:
        return

    if not Company.objects.filter(user=user).exists():
        name = user.email.split('@')[0].replace('.', ' ').replace('_', ' ').title()
        Company.objects.create(user=user, name=name)


def _sync_admin(user, created):
    if user.is_admin and not user.is_staff:
       
        type(user).objects.filter(pk=user.pk).update(is_staff=True)
        user.is_staff = True
