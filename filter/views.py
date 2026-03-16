from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def home(request):
    user = request.user
    return render(request, 'pages/home.html', context={'user': user})
