from django.contrib.auth.decorators import user_passes_test

ROLES_PERMITIDOS = {'admin', 'soporte', 'control_nino'}


def es_control_nino(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    perfil = getattr(user, 'perfilusuario', None)
    return bool(perfil) and perfil.rol in ROLES_PERMITIDOS


control_nino_required = user_passes_test(es_control_nino, login_url='index')
