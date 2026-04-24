from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from ..models import Evento
from .registros_views import actualizar_estados_eventos

@login_required
def dashboard(request):
    # Verificar que el usuario tenga el rol 'soporte', 'parque' o 'admin'
    if hasattr(request.user, 'perfilusuario') and request.user.perfilusuario.rol.lower() in ['soporte', 'parque', 'admin']:
        actualizar_estados_eventos()
        ahora = timezone.now()
        # Eventos futuros ordenados por inicio
        eventos_proximos = Evento.objects.filter(fecha_inicio__gte=ahora, estado='PROGRAMADO').order_by('fecha_inicio')[:5]
        
        # Eventos en curso
        eventos_en_curso = Evento.objects.filter(estado='EN_CURSO').order_by('fecha_inicio')
        
        # Eventos pasados pendientes de cierre ordenados por inicio
        eventos_por_finalizar = Evento.objects.filter(
            fecha_fin__lt=ahora, 
            estado__in=['PROGRAMADO', 'EN_CURSO']
        ).order_by('fecha_inicio')

        context = {
            'fecha_hoy': ahora,
            'eventos_proximos': eventos_proximos,
            'eventos_en_curso': eventos_en_curso,
            'eventos_por_finalizar': eventos_por_finalizar,
        }
        return render(request, 'parque/dashboard.html', context)
    else:
        messages.error(request, "No tienes permisos para acceder a la sección del Parque.")
        return redirect('index')
