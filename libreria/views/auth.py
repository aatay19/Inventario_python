from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, resolve_url


class HubLoginView(LoginView):
    """Login que siempre lleva al hub, ignorando el parámetro ?next=.

    Sin esto, si el usuario abría la raíz "/" sin sesión, Django añadía
    ?next=/ y tras iniciar sesión lo mandaba al inventario en lugar del hub.
    """

    template_name = 'login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        return resolve_url(settings.LOGIN_REDIRECT_URL)

# --- Grupos de roles ---

ROLES_PLENO_ACCESO = ['admin', 'inventario', 'soporte', 'supervisor_inventario']
ROLES_INVENTARIO = [
    'admin',
    'inventario',
    'soporte',
    'supervisor_inventario',
    'almacenista',
]
ROLES_ALMACEN = [
    'admin',
    'inventario',
    'soporte',
    'supervisor_inventario',
    'almacenista',
]
ROLES_GESTION_PEDIDOS = ['admin', 'soporte']


def custom_logout(request):
    logout(request)
    return redirect('login')


# --- Decoradores para verificar roles ---

def es_soporte_gestion(user):
    """Gestión de usuarios y respaldos: exclusivo del rol Soporte.

    El rol Administrador no puede ver ni acceder a Usuarios ni a Copia de
    Respaldo. Un superusuario sin perfil conserva el acceso de emergencia.
    """
    if not user.is_authenticated:
        return False
    perfil = getattr(user, 'perfilusuario', None)
    if perfil is not None:
        return perfil.rol.lower() == 'soporte'
    return user.is_superuser


def es_inventario_acceso(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and perfil.rol.lower() in ROLES_INVENTARIO


def es_almacenista_o_superior(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and perfil.rol.lower() in ROLES_ALMACEN


def es_pleno_acceso(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and perfil.rol.lower() in ROLES_PLENO_ACCESO


def es_gestion_pedidos(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and perfil.rol.lower() in ROLES_GESTION_PEDIDOS


def es_soporte(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and perfil.rol.lower() == 'soporte'


# --- Restricción de borrado para el rol Administrador ---

def puede_eliminar(user):
    """El rol Administrador no puede eliminar registros de ningún módulo."""
    if not user.is_authenticated:
        return False
    perfil = getattr(user, 'perfilusuario', None)
    if perfil is not None and perfil.rol.lower() == 'admin':
        return False
    return user.is_superuser or perfil is not None


def eliminar_permitido(redirect_to='index'):
    """Bloquea las vistas de eliminación para el rol Administrador."""

    def decorador(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if not puede_eliminar(request.user):
                messages.error(
                    request,
                    'El rol Administrador no tiene permiso para eliminar registros.',
                )
                return redirect(redirect_to)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorador
