from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from .forms import CustomLoginForm

@login_required
def home(request):
    return render(request, 'home.html')

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    authentication_form = CustomLoginForm
