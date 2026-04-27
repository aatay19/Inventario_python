from django.shortcuts import redirect
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required

def custom_logout(request):
    logout(request)
    return redirect('login')

# --- Decoradores para verificar roles ---

def es_admin(user):
    if not hasattr(user, 'perfilusuario'): return False
    return user.perfilusuario.rol.lower() in ['admin', 'soporte']

def es_inventario_acceso(user):
    if not hasattr(user, 'perfilusuario'): return False
    return user.perfilusuario.rol.lower() in ['admin', 'inventario', 'consulta', 'soporte', 'supervisor']

def es_pleno_acceso(user):
    if not hasattr(user, 'perfilusuario'): return False
    return user.perfilusuario.rol.lower() in ['admin', 'inventario', 'soporte', 'supervisor']

def es_gestion_pedidos(user):
    if not hasattr(user, 'perfilusuario'): return False
    return user.perfilusuario.rol.lower() in ['admin', 'consulta', 'soporte']

def es_soporte(user):
    if not hasattr(user, 'perfilusuario'): return False
    return user.perfilusuario.rol.lower() == 'soporte'
