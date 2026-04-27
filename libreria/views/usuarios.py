from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator
from .auth import es_admin
from ..models import PerfilUsuario
from ..forms import UserForm, PerfilUsuarioForm

@login_required
@user_passes_test(es_admin, login_url='index')
def usuarios_index(request):
    q = request.GET.get('q', '').strip()
    page_size = 10
    qs = PerfilUsuario.objects.select_related('user').all()
    if q:
        qs = qs.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(direccion__icontains=q) |
            Q(telefono__icontains=q)
        )
    paginator = Paginator(qs.order_by('user__first_name'), page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'usuarios/index.html', {'page_obj': page_obj, 'q': q})

@login_required
@user_passes_test(es_admin, login_url='index')
def usuarios_crear(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        perfil_form = PerfilUsuarioForm(request.POST)
        if user_form.is_valid() and perfil_form.is_valid():
            user = user_form.save()
            perfil = user.perfilusuario
            perfil_form = PerfilUsuarioForm(request.POST, instance=perfil)
            if perfil_form.is_valid():
                perfil_form.save()
                messages.success(request, 'Usuario creado exitosamente.')
                return redirect('usuarios.index')
    else:
        user_form = UserForm()
        perfil_form = PerfilUsuarioForm()
    return render(request, 'usuarios/crear.html', {'user_form': user_form, 'perfil_form': perfil_form})

@login_required
@user_passes_test(es_admin, login_url='index')
def usuarios_editar(request, id):
    perfil = get_object_or_404(PerfilUsuario, id=id)
    user = perfil.user
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=user)
        perfil_form = PerfilUsuarioForm(request.POST, instance=perfil)
        if user_form.is_valid() and perfil_form.is_valid():
            user_form.save()
            perfil_form.save()
            messages.success(request, 'Usuario actualizado exitosamente.')
            return redirect('usuarios.index')
    else:
        user_form = UserForm(instance=user)
        perfil_form = PerfilUsuarioForm(instance=perfil)
    return render(request, 'usuarios/editar.html', {'user_form': user_form, 'perfil_form': perfil_form})

@login_required
@user_passes_test(es_admin, login_url='index')
def usuarios_eliminar(request, id):
    perfil = get_object_or_404(PerfilUsuario, id=id)
    perfil.user.delete()
    messages.success(request, 'Usuario eliminado exitosamente.')
    return redirect('usuarios.index')
