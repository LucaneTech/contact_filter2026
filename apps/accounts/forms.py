from django import forms
from django.contrib.auth.forms import AuthenticationForm


class EmailLoginForm(AuthenticationForm):
    """Formulaire de connexion par email."""
    username = forms.EmailField(
        label='Email',
        widget=forms.EmailInput(attrs={
            'class': 'w-full rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-white placeholder-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500',
            'placeholder': 'votre@email.com',
            'autofocus': True,
        })
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={
            'class': 'w-full rounded-lg border border-slate-600 bg-slate-800 px-4 py-2 text-white placeholder-slate-400 focus:border-blue-500 focus:ring-1 focus:ring-blue-500',
            'placeholder': '••••••••',
        })
    )
