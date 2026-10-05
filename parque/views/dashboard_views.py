from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
import json
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


@login_required
def calendario(request):
    """Vista del calendario con todos los eventos registrados."""
    if hasattr(request.user, 'perfilusuario') and request.user.perfilusuario.rol.lower() in ['soporte', 'parque', 'admin']:
        actualizar_estados_eventos()

        # Colores por estado
        COLOR_MAP = {
            'PROGRAMADO': '#0d6efd',   # azul
            'EN_CURSO':   '#ffc107',   # amarillo
            'FINALIZADO': '#198754',   # verde
            'CANCELADO':  '#dc3545',   # rojo
        }

        eventos = Evento.objects.all()
        eventos_json = []
        for ev in eventos:
            color = COLOR_MAP.get(ev.estado, '#6c757d')

            if ev.hora_inicio:
                start_str = f"{ev.fecha_inicio.strftime('%Y-%m-%d')}T{ev.hora_inicio.strftime('%H:%M:%S')}"
            else:
                start_str = ev.fecha_inicio.strftime('%Y-%m-%d')

            # No pasamos 'end' para que el evento quede confinado al recuadro del día de inicio.
            # Si la fecha_fin cae en otro día, FullCalendar lo dibujaría como multi-día.
            eventos_json.append({
                'id': ev.pk,
                'title': ev.titulo,
                'start': start_str,
                'color': color,
                'extendedProps': {
                    'estado': ev.get_estado_display(),
                    'zona': ev.zona or '',
                    'nombre_reserva': ev.nombre_reserva or '',
                    'url_detalle': f'/parque/eventos/detalle/{ev.pk}/',
                },
            })

        context = {
            'eventos_json': json.dumps(eventos_json),
        }
        return render(request, 'parque/calendario.html', context)
    else:
        messages.error(request, "No tienes permisos para acceder a la sección del Parque.")
        return redirect('index')
