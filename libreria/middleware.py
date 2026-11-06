from django.contrib import messages
from django.shortcuts import redirect

# Roles que no deben acceder al módulo del Parque.
ROLES_SIN_PARQUE = {"supervisor_inventario", "supervisor_caja", "cuadre_caja"}


class RestriccionParqueMiddleware:
    """Evita que los roles de inventario/caja entren al módulo del Parque."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.path_info.startswith("/parque/")
        ):
            perfil = getattr(request.user, "perfilusuario", None)
            rol = getattr(perfil, "rol", None) if perfil else None
            if rol in ROLES_SIN_PARQUE:
                messages.error(
                    request,
                    "Tu rol no tiene acceso al módulo del Parque.",
                )
                return redirect("index")

        return self.get_response(request)
