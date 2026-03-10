from django.contrib.auth.forms import AuthenticationForm
from django import forms

class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500', }))
    email = forms.CharField(widget=forms.EmailInput(attrs={'class': 'rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500', }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'rounded-md border border-gray-300 focus:outline-none focus:ring-2 focus:ring-blue-500', }))
    