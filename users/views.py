from django.shortcuts import render
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from .forms import CustomLoginForm
from django.urls import reverse_lazy
from django.contrib.auth.views import PasswordResetView
from django.contrib.messages.views import SuccessMessageMixin


def SuccesResetPassword(request):
    return render(request, 'registration/pages/succes.html')

class CustomLoginView(LoginView):
    template_name = 'registration/pages/login.html'
    authentication_form = CustomLoginForm
    
class CustomPasswordResetView(SuccessMessageMixin, PasswordResetView):
    template_name = "registration/pages/password_reset_form.html"
    email_template_name = 'registration/pages/password_reset_email.html'
    subject_template_name = 'registration/pages/password_reset_subject.txt'
    success_message = "Nous vous avons envoyé par courriel les instructions pour définir votre mot de passe,si un compte existe avec l'adresse courriel que vous avez saisie. Vous devriez les recevoir sous peu.Si vous ne recevez pas de courriel,veuillez vérifier que vous avez bien saisi l'adresse avec laquelle vous vous êtes inscrit et vérifiez votre dossier de courriers indésirables. »"
