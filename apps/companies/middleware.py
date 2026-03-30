
from django.utils.deprecation import MiddlewareMixin


class CompanyMiddleware(MiddlewareMixin):
    """Attache la company à la request pour les utilisateurs liés à une entreprise."""

    def process_request(self, request):
        request.company = None
        if request.user.is_authenticated:
            try:
                request.company = request.user.company
            except Exception:
                pass
