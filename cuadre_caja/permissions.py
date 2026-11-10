from django.contrib.auth.decorators import user_passes_test

ROLES_CUADRE = {'admin', 'soporte', 'supervisor', 'supervisor_caja', 'supervisor_cuadre_caja', 'cuadre_caja'}
ROLES_SUPERVISOR = {'admin', 'soporte', 'supervisor', 'supervisor_caja', 'supervisor_cuadre_caja'}


def _tiene_perfil(user, roles):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and getattr(perfil, 'rol', None) in roles


def es_cuadre_caja(user):
    """Usuario cuyo rol es exactamente cuadre_caja (sin ser admin/supervisor)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return False
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and getattr(perfil, 'rol', None) in {'cuadre_caja', 'supervisor_caja', 'supervisor_cuadre_caja'}


def puede_gestionar_cuadre(user):
    """Acceso a vistas de Cuadre de Caja (incluye rol cuadre_caja)."""
    return _tiene_perfil(user, ROLES_CUADRE)


def es_supervisor_o_superior(user):
    """Acceso restringido a Supervisor de Caja y roles superiores."""
    return _tiene_perfil(user, ROLES_SUPERVISOR)


cuadre_caja_required = user_passes_test(
    puede_gestionar_cuadre, login_url='index'
)

supervisor_required = user_passes_test(
    es_supervisor_o_superior, login_url='index'
)
