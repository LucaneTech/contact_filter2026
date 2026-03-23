from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'is_company', 'is_admin', 'is_staff', 'date_joined')
    list_filter = ('is_company', 'is_admin', 'is_staff')
    search_fields = ('email',)
    ordering = ('-date_joined',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Rôles', {'fields': ('is_company', 'is_admin', 'is_staff', 'is_superuser', 'is_active')}),
        ('Dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {'fields': ('email', 'password1', 'password2')}),
        ('Rôles', {'fields': ('is_company', 'is_admin', 'is_staff')}),
    )
