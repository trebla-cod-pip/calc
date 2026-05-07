"""
Middleware: все URL под /calculator/ требуют авторизации.
Неавторизованные пользователи перенаправляются на /login/.
"""
from django.conf import settings
from django.shortcuts import redirect


class LoginRequiredMiddleware:
    """
    Требует авторизации для всех URL, начинающихся с /calculator/.
    Публичные URL (логин, логаут, админка) исключены.
    """

    OPEN_PREFIXES = ('/login/', '/logout/', '/admin/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Пропускаем публичные маршруты
        if any(path.startswith(p) for p in self.OPEN_PREFIXES):
            return self.get_response(request)

        # Все остальные маршруты — требуем авторизацию
        if not request.user.is_authenticated:
            # Для HTMX-запросов возвращаем 401 чтобы браузер перегрузил страницу
            if request.headers.get('HX-Request'):
                response = redirect(settings.LOGIN_URL)
                response['HX-Redirect'] = settings.LOGIN_URL
                return response
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")

        return self.get_response(request)
