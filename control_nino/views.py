from collections import defaultdict
from datetime import datetime, date, time, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.utils.http import url_has_allowed_host_and_scheme
from fpdf import FPDF

from .models import ControlNino, Fiesta, BrazaleteFiesta, Novedad, TIEMPO_MAXIMO, TIEMPO_MAXIMO_NINO
from .forms import ControlNinoForm, FiestaForm, NovedadManualForm
from .permissions import control_nino_required, control_nino_gestion_required


def _rango_dia(dia):
    """Devuelve el rango [inicio, fin) con zona horaria para un día dado."""
    inicio = timezone.make_aware(datetime.combine(dia, time.min))
    return inicio, inicio + timedelta(days=1)


def registrar_novedad_sistema(titulo, descripcion, usuario=None, nino=None, fiesta=None):
    """Registra automáticamente una novedad/log del sistema."""
    try:
        Novedad.objects.create(
            tipo='SISTEMA',
            titulo=titulo,
            descripcion=descripcion,
            usuario=usuario,
            nino=nino,
            fiesta=fiesta,
        )
    except Exception:
        pass


def _finalizar_vencidos():
    """Finaliza niños y fiestas de días anteriores que quedaron sin salida.

    La salida se fija en la hora de fin contratada (ingreso/inicio + tiempo)
    para que las estadísticas cuenten como máximo el tiempo del servicio.
    """
    hoy = timezone.localdate()
    clave_cache = f'control_nino_vencidos_{hoy.isoformat()}'
    if cache.get(clave_cache):
        return

    inicio_hoy, _ = _rango_dia(hoy)

    ninos = list(ControlNino.objects.filter(
        hora_salida__isnull=True, fecha_registro__lt=inicio_hoy
    ))
    for nino in ninos:
        nino.hora_salida = nino.fecha_registro + timedelta(minutes=nino.tiempo)
    if ninos:
        ControlNino.objects.bulk_update(ninos, ['hora_salida'])

    fiestas = list(Fiesta.objects.filter(
        hora_salida__isnull=True, fecha_registro__lt=inicio_hoy
    ))
    for fiesta in fiestas:
        if not fiesta.hora_inicio:
            fiesta.hora_inicio = fiesta.fecha_registro
        fiesta.hora_salida = fiesta.hora_inicio + timedelta(minutes=fiesta.tiempo)
    if fiestas:
        Fiesta.objects.bulk_update(fiestas, ['hora_inicio', 'hora_salida'])

    cache.set(clave_cache, True, 60 * 60 * 24)


@login_required
@control_nino_required
def lista_control_ninos(request):
    """Página principal: solo lo del día de hoy (se limpia sola cada día)."""
    _finalizar_vencidos()
    hoy = timezone.localdate()
    inicio, fin = _rango_dia(hoy)
    ahora = timezone.now()

    ninos = ControlNino.objects.filter(
        fecha_registro__gte=inicio, fecha_registro__lt=fin
    ).prefetch_related('novedades').annotate(
        orden_activo=Case(
            When(hora_salida__isnull=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('orden_activo', 'fecha_registro')
    fiestas = Fiesta.objects.filter(
        fecha_registro__gte=inicio, fecha_registro__lt=fin
    ).prefetch_related('brazaletes').annotate(
        orden_activo=Case(
            When(hora_salida__isnull=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        )
    ).order_by('orden_activo', '-fecha_registro')

    historico_ninos = ControlNino.objects.exclude(
        fecha_registro__gte=inicio, fecha_registro__lt=fin
    ).count()
    historico_fiestas = Fiesta.objects.exclude(
        fecha_registro__gte=inicio, fecha_registro__lt=fin
    ).count()

    ms_hasta_medianoche = int((fin - ahora).total_seconds() * 1000)

    return render(request, 'control_nino/lista.html', {
        'ninos': ninos,
        'fiestas': fiestas,
        'ahora_ms': int(ahora.timestamp() * 1000),
        'hoy': hoy,
        'ms_hasta_medianoche': ms_hasta_medianoche,
        'historico_total': historico_ninos + historico_fiestas,
        'tiempo_maximo': TIEMPO_MAXIMO,
        'tiempo_maximo_nino': TIEMPO_MAXIMO_NINO,
    })


@login_required
@control_nino_required
def crear_control_nino(request):
    if request.method == 'POST':
        form = ControlNinoForm(request.POST)
        if form.is_valid():
            nino = form.save()
            if request.POST.get('agregar_otro'):
                messages.success(request, f"Niño '{nino.nombre}' registrado con {nino.tiempo} minutos. Puedes agregar otro.")
                return redirect('control_nino:crear_control_nino')
            messages.success(request, f"Niño '{nino.nombre}' registrado con {nino.tiempo} minutos.")
            return redirect('control_nino:lista_control_ninos')
    else:
        form = ControlNinoForm()
    return render(request, 'control_nino/form.html', {'form': form, 'titulo': 'Agregar Niño'})


@login_required
@control_nino_required
def editar_control_nino(request, pk):
    nino = get_object_or_404(ControlNino, pk=pk)
    if request.method == 'POST':
        prev_nombre = nino.nombre
        prev_descripcion = nino.descripcion or ''
        prev_tiempo = nino.tiempo
        prev_tiempo_adicional = nino.tiempo_adicional
        prev_brazaletes_adicionales = nino.brazaletes_adicionales

        form = ControlNinoForm(request.POST, instance=nino)
        if form.is_valid():
            nino = form.save(commit=False)
            if nino.tiempo == prev_tiempo:
                nino.tiempo_adicional = prev_tiempo_adicional
                nino.brazaletes_adicionales = prev_brazaletes_adicionales
            else:
                if nino.tiempo < nino.tiempo_adicional:
                    nino.tiempo_adicional = 0
            nino.save()
            cambios = []
            if prev_nombre != nino.nombre:
                cambios.append(f"Nombre: '{prev_nombre}' ➜ '{nino.nombre}'")
            if prev_descripcion != (nino.descripcion or ''):
                cambios.append(f"Descripción: '{prev_descripcion or 'Sin descripción'}' ➜ '{nino.descripcion or 'Sin descripción'}'")
            if prev_tiempo != nino.tiempo:
                cambios.append(f"Tiempo: {prev_tiempo} min ➜ {nino.tiempo} min")

            desc_novedad = " | ".join(cambios) if cambios else "Se guardó el registro sin cambios en sus campos principales."
            registrar_novedad_sistema(
                titulo=f"Niño editado: {nino.nombre}",
                descripcion=desc_novedad,
                usuario=request.user,
                nino=nino
            )
            messages.success(request, f"Datos del niño '{nino.nombre}' actualizados correctamente.")
            return redirect('control_nino:lista_control_ninos')
    else:
        form = ControlNinoForm(instance=nino)
    return render(request, 'control_nino/form.html', {
        'form': form,
        'titulo': f'Editar Niño: {nino.nombre}',
        'es_edicion': True,
        'nino': nino,
    })


@login_required
@control_nino_required
def agregar_tiempo_nino(request, pk):
    """Suma 1 o 45 minutos al tiempo total de un niño, sin superar el máximo de 90 min."""
    nino = get_object_or_404(ControlNino, pk=pk)
    es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405) if es_ajax else redirect('control_nino:lista_control_ninos')

    try:
        minutos = int(request.POST.get('minutos', 45))
    except (TypeError, ValueError):
        minutos = 45

    error = None
    if minutos != 45:
        error = 'Solo se permite agregar 45 minutos.'
    elif nino.salio:
        error = 'El niño ya tiene salida registrada.'
    elif nino.tiempo >= TIEMPO_MAXIMO_NINO:
        error = f"El niño ya alcanzó el máximo de {TIEMPO_MAXIMO_NINO} minutos."
    elif nino.tiempo + minutos > TIEMPO_MAXIMO_NINO:
        error = f"Los niños no pueden superar los {TIEMPO_MAXIMO_NINO} minutos en total."

    if error:
        if es_ajax:
            return JsonResponse({'ok': False, 'error': error, 'tiempo': nino.tiempo}, status=400)
        messages.error(request, error)
    else:
        tiempo_ant = nino.tiempo
        tiempo_culminado = nino.segundos_restantes <= 0
        nino.tiempo += minutos
        nino.tiempo_adicional += minutos
        update_fields = ['tiempo', 'tiempo_adicional']

        # Si se añaden 45 min, se cuenta como un brazalete nuevo en la estadística
        if minutos == 45:
            nino.brazaletes_adicionales += 1
            update_fields.append('brazaletes_adicionales')
            # Si culminó su tiempo, reajustar el conteo para que tenga los 45 min completos desde ahora
            if tiempo_culminado:
                nino.fecha_registro = timezone.now() - timedelta(minutes=tiempo_ant)
                update_fields.append('fecha_registro')

        nino.save(update_fields=update_fields)

        detalle_extra = " (nuevo brazalete de 45 min tras culminar tiempo)" if (minutos == 45 and tiempo_culminado) else (" (nuevo brazalete de 45 min)" if minutos == 45 else "")
        registrar_novedad_sistema(
            titulo=f"Tiempo añadido a niño: {nino.nombre}",
            descripcion=f"Se agregaron +{minutos} min al niño '{nino.nombre}'{detalle_extra}. Tiempo anterior: {tiempo_ant} min ➜ Nuevo tiempo: {nino.tiempo} min.",
            usuario=request.user,
            nino=nino
        )
        if not es_ajax:
            messages.success(request, f"Se agregaron {minutos} minutos al niño '{nino.nombre}'.")

    if es_ajax:
        return JsonResponse({'ok': error is None, 'tiempo': nino.tiempo, 'error': error})

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect('control_nino:lista_control_ninos')


@login_required
@control_nino_required
def eliminar_control_nino(request, pk):
    nino = get_object_or_404(ControlNino, pk=pk)
    if request.method == 'POST':
        nombre_nino = nino.nombre
        nino.delete()
        messages.success(request, "Registro de niño eliminado.")
        return redirect('control_nino:lista_control_ninos')
    return render(request, 'control_nino/eliminar.html', {'nino': nino})


@login_required
@control_nino_required
def marcar_salida(request, pk):
    nino = get_object_or_404(ControlNino, pk=pk)
    if request.method == 'POST':
        if not nino.hora_salida:
            nino.hora_salida = timezone.now()
            nino.save(update_fields=['hora_salida'])
            messages.success(request, f"Salida registrada para '{nino.nombre}'.")
        else:
            messages.info(request, f"'{nino.nombre}' ya tenía salida registrada.")
    return redirect('control_nino:lista_control_ninos')


@login_required
@control_nino_required
def deshacer_salida(request, pk):
    nino = get_object_or_404(ControlNino, pk=pk)
    if request.method == 'POST':
        nino.hora_salida = None
        nino.save(update_fields=['hora_salida'])
        messages.success(request, f"Salida de '{nino.nombre}' eliminada.")
    return redirect('control_nino:lista_control_ninos')


@login_required
@control_nino_required
def registrar_incidente_nino(request, pk):
    """Permite registrar un incidente u observación especial sobre un niño y guardarlo en la bitácora/novedades."""
    nino = get_object_or_404(ControlNino, pk=pk)
    es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST':
        if es_ajax:
            return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)
        return redirect('control_nino:lista_control_ninos')

    titulo = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()

    if not descripcion:
        error_msg = "Debes ingresar una descripción detallada del incidente."
        if es_ajax:
            return JsonResponse({'ok': False, 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('control_nino:lista_control_ninos')

    if not titulo:
        titulo = f"Incidente: {nino.nombre}"

    novedad = Novedad.objects.create(
        tipo='INCIDENTE',
        titulo=titulo,
        descripcion=descripcion,
        usuario=request.user,
        nino=nino
    )

    msg = f"Incidente registrado correctamente para el niño '{nino.nombre}'."
    if es_ajax:
        return JsonResponse({
            'ok': True,
            'mensaje': msg,
            'novedad': {
                'id': novedad.pk,
                'titulo': novedad.titulo,
                'descripcion': novedad.descripcion,
                'fecha': timezone.localtime(novedad.fecha_registro).strftime('%d/%m/%Y %H:%M'),
                'usuario': request.user.username,
            }
        })

    messages.success(request, msg)
    return redirect('control_nino:lista_control_ninos')


@login_required
@control_nino_required
def registrar_incidente_fiesta(request, pk):
    """Permite registrar un incidente u observación especial sobre una fiesta y guardarlo en la bitácora/novedades."""
    fiesta = get_object_or_404(Fiesta, pk=pk)
    es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST':
        if es_ajax:
            return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405)
        return redirect('control_nino:lista_control_ninos')

    titulo = request.POST.get('titulo', '').strip()
    descripcion = request.POST.get('descripcion', '').strip()

    if not descripcion:
        error_msg = "Debes ingresar una descripción detallada del incidente."
        if es_ajax:
            return JsonResponse({'ok': False, 'error': error_msg}, status=400)
        messages.error(request, error_msg)
        return redirect('control_nino:lista_control_ninos')

    if not titulo:
        titulo = f"Incidente: {fiesta.nombre}"

    novedad = Novedad.objects.create(
        tipo='INCIDENTE',
        titulo=titulo,
        descripcion=descripcion,
        usuario=request.user,
        fiesta=fiesta
    )

    msg = f"Incidente registrado correctamente para la fiesta '{fiesta.nombre}'."
    if es_ajax:
        return JsonResponse({
            'ok': True,
            'mensaje': msg,
            'novedad': {
                'id': novedad.pk,
                'titulo': novedad.titulo,
                'descripcion': novedad.descripcion,
                'fecha': timezone.localtime(novedad.fecha_registro).strftime('%d/%m/%Y %H:%M'),
                'usuario': request.user.username,
            }
        })

    messages.success(request, msg)
    return redirect('control_nino:lista_control_ninos')


def _control_ninos_queryset(fecha_str):
    """Devuelve el queryset filtrado por fecha (YYYY-MM-DD) si se indica."""
    qs = ControlNino.objects.all().order_by('fecha_registro')
    fecha = None
    if fecha_str:
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            inicio, fin = _rango_dia(fecha)
            qs = qs.filter(fecha_registro__gte=inicio, fecha_registro__lt=fin)
        except ValueError:
            fecha = None
    return qs, fecha


@login_required
@control_nino_required
@control_nino_gestion_required
def reporte_control_ninos(request):
    _finalizar_vencidos()
    fecha_str = request.GET.get('fecha', '').strip()
    ninos, fecha = _control_ninos_queryset(fecha_str)
    total = ninos.count()
    salidos = ninos.filter(hora_salida__isnull=False).count()
    return render(request, 'control_nino/reporte.html', {
        'ninos': ninos,
        'fecha': fecha_str,
        'total': total,
        'salidos': salidos,
        'pendientes': total - salidos,
    })


@login_required
@control_nino_required
@control_nino_gestion_required
def reporte_control_ninos_pdf(request):
    _finalizar_vencidos()
    fecha_str = request.GET.get('fecha', '').strip()
    ninos, fecha = _control_ninos_queryset(fecha_str)
    titulo_fecha = f"Fecha: {fecha.strftime('%d/%m/%Y')}" if fecha else "Todos los registros"

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(190, 10, txt="REPORTE CONTROL NINO", ln=True, align='C')
    pdf.set_font("Helvetica", size=11)
    pdf.cell(190, 7, txt=titulo_fecha, ln=True, align='C')
    pdf.ln(5)

    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(42, 8, txt="Nombre", border=1, fill=True)
    pdf.cell(48, 8, txt="Descripcion", border=1, fill=True)
    pdf.cell(16, 8, txt="Tiempo", border=1, fill=True, align='C')
    pdf.cell(28, 8, txt="Ingreso", border=1, fill=True, align='C')
    pdf.cell(28, 8, txt="Salida", border=1, fill=True, align='C')
    pdf.cell(24, 8, txt="Estancia", border=1, fill=True, align='C')
    pdf.ln()

    pdf.set_font("Helvetica", size=9)
    total = ninos.count()
    for n in ninos:
        ingreso = timezone.localtime(n.fecha_registro).strftime('%d/%m %H:%M')
        if n.hora_salida:
            salida = timezone.localtime(n.hora_salida).strftime('%d/%m %H:%M')
        else:
            salida = 'Pendiente'
        pdf.cell(42, 8, txt=(n.nombre or '')[:20], border=1)
        pdf.cell(48, 8, txt=(n.descripcion or '')[:30], border=1)
        pdf.cell(16, 8, txt=f"{n.tiempo}", border=1, align='C')
        pdf.cell(28, 8, txt=ingreso, border=1, align='C')
        pdf.cell(28, 8, txt=salida, border=1, align='C')
        pdf.cell(24, 8, txt=f"{n.minutos_estancia} min", border=1, align='C')
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 11)
    pdf.cell(190, 8, txt=f"Total de registros: {total}", ln=True)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_control_nino.pdf"'

    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        response.write(pdf_output.encode('latin-1', 'replace'))
    elif isinstance(pdf_output, bytearray):
        response.write(bytes(pdf_output))
    else:
        response.write(pdf_output)
    return response


def _pdf_response(pdf, filename):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    output = pdf.output(dest='S')
    if isinstance(output, str):
        response.write(output.encode('latin-1', 'replace'))
    elif isinstance(output, bytearray):
        response.write(bytes(output))
    else:
        response.write(output)
    return response


@login_required
@control_nino_required
@control_nino_gestion_required
def reporte_control_nino_pdf(request, pk):
    """Reporte PDF individual de un niño."""
    _finalizar_vencidos()
    nino = get_object_or_404(ControlNino, pk=pk)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(190, 10, txt="REPORTE DE NINO", ln=True, align='C')
    pdf.ln(4)

    filas = [
        ("Nombre", nino.nombre),
        ("Descripcion", nino.descripcion or '-'),
        ("Tiempo asignado", f"{nino.tiempo} min"),
        ("Ingreso", timezone.localtime(nino.fecha_registro).strftime('%d/%m/%Y %H:%M')),
        ("Salida", timezone.localtime(nino.hora_salida).strftime('%d/%m/%Y %H:%M') if nino.hora_salida else 'Pendiente'),
        ("Estancia", f"{nino.minutos_estancia} min"),
        ("Estado", "Salio" if nino.salio else "En el parque"),
    ]
    for etiqueta, valor in filas:
        pdf.set_font("Helvetica", 'B', 11)
        pdf.cell(55, 9, txt=f"{etiqueta}:", border=1)
        pdf.set_font("Helvetica", size=11)
        pdf.cell(130, 9, txt=str(valor), border=1, ln=True)

    return _pdf_response(pdf, 'reporte_nino.pdf')


@login_required
@control_nino_required
@control_nino_gestion_required
def reporte_fiesta_pdf(request, pk):
    """Reporte PDF individual de una fiesta con su lista de brazaletes."""
    _finalizar_vencidos()
    fiesta = get_object_or_404(Fiesta.objects.prefetch_related('brazaletes'), pk=pk)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(190, 10, txt="REPORTE DE FIESTA", ln=True, align='C')
    pdf.ln(4)

    info = [
        ("Fiesta", fiesta.nombre),
        ("Tiempo", f"{fiesta.tiempo} min"),
        ("Brazaletes", f"{fiesta.cantidad_brazaletes}"),
        ("Ingreso", timezone.localtime(fiesta.fecha_registro).strftime('%d/%m/%Y %H:%M')),
        ("Inicio", timezone.localtime(fiesta.hora_inicio).strftime('%d/%m/%Y %H:%M') if fiesta.hora_inicio else 'Sin iniciar'),
        ("Salida", timezone.localtime(fiesta.hora_salida).strftime('%d/%m/%Y %H:%M') if fiesta.hora_salida else 'Pendiente'),
    ]
    for etiqueta, valor in info:
        pdf.set_font("Helvetica", 'B', 11)
        pdf.cell(40, 9, txt=f"{etiqueta}:", border=1)
        pdf.set_font("Helvetica", size=11)
        pdf.cell(150, 9, txt=str(valor), border=1, ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(20, 8, txt="N.", border=1, fill=True, align='C')
    pdf.cell(85, 8, txt="Nombre", border=1, fill=True)
    pdf.cell(85, 8, txt="Descripcion", border=1, fill=True, ln=True)

    pdf.set_font("Helvetica", size=9)
    for b in fiesta.brazaletes.all():
        pdf.cell(20, 8, txt=str(b.numero), border=1, align='C')
        pdf.cell(85, 8, txt=(b.nombre or '-')[:40], border=1)
        pdf.cell(85, 8, txt=(b.descripcion or '-')[:40], border=1, ln=True)

    return _pdf_response(pdf, 'reporte_fiesta.pdf')


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except ValueError:
        return None


@login_required
@control_nino_required
@control_nino_gestion_required
def historial_control_ninos(request):
    """Historial de niños y fiestas agrupado por día."""
    _finalizar_vencidos()
    desde_str = request.GET.get('desde', '').strip()
    hasta_str = request.GET.get('hasta', '').strip()

    ninos_qs = ControlNino.objects.all()
    fiestas_qs = Fiesta.objects.all()

    desde = _parse_fecha(desde_str)
    hasta = _parse_fecha(hasta_str)
    if desde:
        inicio, _ = _rango_dia(desde)
        ninos_qs = ninos_qs.filter(fecha_registro__gte=inicio)
        fiestas_qs = fiestas_qs.filter(fecha_registro__gte=inicio)
    if hasta:
        _, fin = _rango_dia(hasta)
        ninos_qs = ninos_qs.filter(fecha_registro__lt=fin)
        fiestas_qs = fiestas_qs.filter(fecha_registro__lt=fin)

    # Recopilar todos los días que tienen datos
    dias_con_datos = set()
    for dt in ninos_qs.values_list('fecha_registro', flat=True).iterator():
        dias_con_datos.add(timezone.localtime(dt).date())
    for dt in fiestas_qs.values_list('fecha_registro', flat=True).iterator():
        dias_con_datos.add(timezone.localtime(dt).date())

    # Si hay filtro de rango, rellenar también los días vacíos del rango
    if desde and hasta and desde <= hasta:
        from datetime import timedelta as _td
        dia_iter = desde
        while dia_iter <= hasta:
            dias_con_datos.add(dia_iter)
            dia_iter += _td(days=1)
    elif desde and not hasta:
        # Desde hasta hoy (localdate)
        from datetime import timedelta as _td
        hoy_local = timezone.localdate()
        dia_iter = desde
        while dia_iter <= hoy_local:
            dias_con_datos.add(dia_iter)
            dia_iter += _td(days=1)
    elif hasta and not desde:
        # Rellenar desde el mínimo existente hasta la fecha hasta
        if dias_con_datos:
            from datetime import timedelta as _td
            fecha_min = min(dias_con_datos)
            dia_iter = fecha_min
            while dia_iter <= hasta:
                dias_con_datos.add(dia_iter)
                dia_iter += _td(days=1)

    dias = sorted(dias_con_datos, reverse=True)
    paginator = Paginator(dias, 10)
    page = paginator.get_page(request.GET.get('page'))
    page_dias = list(page.object_list)

    dias_data = []
    if page_dias:
        inicio_pagina, _ = _rango_dia(min(page_dias))
        _, fin_pagina = _rango_dia(max(page_dias))

        ninos_page = ninos_qs.filter(
            fecha_registro__gte=inicio_pagina, fecha_registro__lt=fin_pagina
        ).order_by('fecha_registro')
        fiestas_page = fiestas_qs.filter(
            fecha_registro__gte=inicio_pagina, fecha_registro__lt=fin_pagina
        ).prefetch_related('brazaletes').order_by('-fecha_registro')

        ninos_por_dia = defaultdict(list)
        for nino in ninos_page:
            ninos_por_dia[timezone.localtime(nino.fecha_registro).date()].append(nino)

        fiestas_por_dia = defaultdict(list)
        for fiesta in fiestas_page:
            fiestas_por_dia[timezone.localtime(fiesta.fecha_registro).date()].append(fiesta)

        brazaletes_por_dia = defaultdict(int)
        for dt in BrazaleteFiesta.objects.filter(
            fiesta__fecha_registro__gte=inicio_pagina,
            fiesta__fecha_registro__lt=fin_pagina,
        ).values_list('fiesta__fecha_registro', flat=True).iterator():
            brazaletes_por_dia[timezone.localtime(dt).date()] += 1

        for dia in page_dias:
            ninos = ninos_por_dia.get(dia, [])
            fiestas = fiestas_por_dia.get(dia, [])
            dias_data.append({
                'fecha': dia,
                'ninos': ninos,
                'fiestas': fiestas,
                'total_ninos': len(ninos),
                'total_fiestas': len(fiestas),
                'total_brazaletes': brazaletes_por_dia.get(dia, 0),
                'sin_movimiento': len(ninos) == 0 and len(fiestas) == 0,
            })

    return render(request, 'control_nino/historial.html', {
        'dias': dias_data,
        'page_obj': page,
        'desde': desde_str,
        'hasta': hasta_str,
        'total_dias': paginator.count,
    })


MESES_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]


PRECIO_NINO_45 = 4.50
PRECIO_NINO_90 = 6.99


@login_required
@control_nino_required
@control_nino_gestion_required
def estadisticas_control_ninos(request):
    """Estadísticas agrupadas por periodo (día, semanal, mensual, anual) con recaudación estimada."""
    _finalizar_vencidos()

    periodo = request.GET.get('periodo', 'mensual').strip().lower()
    if periodo not in ('dia', 'semanal', 'mensual', 'anual'):
        periodo = 'mensual'

    anio_filtro = request.GET.get('anio', '').strip()
    mes_filtro = request.GET.get('mes', '').strip()
    fecha_filtro = request.GET.get('fecha', '').strip()
    semana_filtro = request.GET.get('semana', '').strip()

    now = timezone.localtime()
    today = now.date()

    # Recolectar datos
    resumen = defaultdict(lambda: {
        'ninos': 0, 'ninos_45': 0, 'ninos_90': 0, 'ninos_renovados_45': 0,
        'fiestas': 0, 'brazaletes': 0, 'tiempo_fiestas': 0,
    })

    anios_set = set()

    # Niños
    for dt, tiempo, tiempo_adicional, brazaletes_adicionales in ControlNino.objects.values_list(
        'fecha_registro', 'tiempo', 'tiempo_adicional', 'brazaletes_adicionales'
    ).iterator():
        if dt:
            local = timezone.localtime(dt)
            anios_set.add(local.year)
            clave = _obtener_clave_periodo(local, periodo)
            datos = resumen[clave]

            # Cada 45 min añadidos tras culminar cuenta como un brazalete nuevo de 45 min
            braz_extra = max(brazaletes_adicionales or 0, (tiempo_adicional or 0) // 45)

            if braz_extra > 0:
                # 1 brazalete base de 45 min + braz_extra brazaletes nuevos de 45 min
                cant_brazaletes_45 = 1 + braz_extra
                datos['ninos_45'] += cant_brazaletes_45
                datos['ninos'] += cant_brazaletes_45
                datos['ninos_renovados_45'] += braz_extra
            elif tiempo == 90:
                datos['ninos_90'] += 1
                datos['ninos'] += 1
            elif tiempo == 45:
                datos['ninos_45'] += 1
                datos['ninos'] += 1
            else:
                # Opciones de prueba (1 min)
                datos['ninos'] += 1

    # Fiestas
    for dt, tiempo in Fiesta.objects.values_list('fecha_registro', 'tiempo').iterator():
        if dt:
            local = timezone.localtime(dt)
            anios_set.add(local.year)
            clave = _obtener_clave_periodo(local, periodo)
            datos = resumen[clave]
            datos['fiestas'] += 1
            datos['tiempo_fiestas'] += min(tiempo or 0, TIEMPO_MAXIMO)

    # Brazaletes de fiesta
    for dt in BrazaleteFiesta.objects.values_list('fiesta__fecha_registro', flat=True).iterator():
        if dt:
            local = timezone.localtime(dt)
            anios_set.add(local.year)
            clave = _obtener_clave_periodo(local, periodo)
            resumen[clave]['brazaletes'] += 1

    anios = sorted(anios_set, reverse=True)

    # Filtrar claves según año/mes/fecha si aplica para la tabla
    claves_filtradas = []
    for k in resumen.keys():
        anio_k = k[0]
        if anio_filtro.isdigit() and anio_k != int(anio_filtro):
            continue
        if mes_filtro.isdigit() and periodo in ('dia', 'semanal', 'mensual'):
            if periodo in ('dia', 'mensual') and k[1] != int(mes_filtro):
                continue
            if periodo == 'semanal' and k[2].month != int(mes_filtro) and k[3].month != int(mes_filtro):
                continue
        if fecha_filtro and periodo == 'dia':
            try:
                f_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
                if k[3] != f_obj:
                    continue
            except ValueError:
                pass
        if semana_filtro.isdigit() and periodo == 'semanal':
            if k[1] != int(semana_filtro):
                continue
        claves_filtradas.append(k)

    claves_ordenadas = sorted(claves_filtradas, key=lambda c: _sort_clave_periodo(c, periodo), reverse=True)

    # Determinar la clave activa para los CUADROS GRANDES según el periodo seleccionado
    es_periodo_personalizado = False

    if periodo == 'dia':
        fecha_obj = None
        if fecha_filtro:
            try:
                fecha_obj = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
                es_periodo_personalizado = True
            except ValueError:
                fecha_obj = None

        if not fecha_obj:
            if mes_filtro.isdigit():
                # Cuando hay filtro de mes activo, los cuadros grandes deben
                # reflejar el mismo contexto que la tabla (no 'hoy' de otro mes).
                if claves_filtradas:
                    # Usar el dia mas reciente con datos dentro del mes filtrado
                    clave_rec = sorted(claves_filtradas, key=lambda c: c[3], reverse=True)[0]
                    fecha_obj = clave_rec[3]
                    es_periodo_personalizado = (fecha_obj != today)
                else:
                    # Mes seleccionado sin datos: apuntar al 1ro del mes para mostrar ceros
                    try:
                        m_int = int(mes_filtro)
                        yr_int = int(anio_filtro) if anio_filtro.isdigit() else today.year
                        fecha_obj = date(yr_int, m_int, 1)
                        es_periodo_personalizado = True
                    except (ValueError, TypeError):
                        fecha_obj = today
            else:
                fecha_obj = today

        clave_tarjeta = (fecha_obj.year, fecha_obj.month, fecha_obj.day, fecha_obj)
        if fecha_obj == today and not es_periodo_personalizado:
            card_etiqueta = f"Hoy ({today.strftime('%d/%m/%Y')})"
        else:
            card_etiqueta = fecha_obj.strftime('%d/%m/%Y')
        card_titulo = "Resumen del Día"
        card_periodo_nombre = "del día"
        periodo_display = "Por Día"

    elif periodo == 'semanal':
        if semana_filtro.isdigit():
            num_sem = int(semana_filtro)
            yr = int(anio_filtro) if anio_filtro.isdigit() else today.year
            es_periodo_personalizado = True
            clave_existente = [k for k in resumen.keys() if k[0] == yr and k[1] == num_sem]
            if clave_existente:
                clave_tarjeta = clave_existente[0]
            else:
                lunes = date.fromisocalendar(yr, num_sem, 1)
                domingo = lunes + timedelta(days=6)
                clave_tarjeta = (yr, num_sem, lunes, domingo)
            lunes, domingo = clave_tarjeta[2], clave_tarjeta[3]
            card_etiqueta = f"Semana {num_sem} ({lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')})"
        else:
            num_sem = today.isocalendar()[1]
            lunes = today - timedelta(days=today.weekday())
            domingo = lunes + timedelta(days=6)
            clave_tarjeta = (today.year, num_sem, lunes, domingo)
            card_etiqueta = f"Esta Semana ({lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')})"

        card_titulo = "Resumen Semanal"
        card_periodo_nombre = "de la semana"
        periodo_display = "Semanal"

    elif periodo == 'mensual':
        if mes_filtro.isdigit() and 1 <= int(mes_filtro) <= 12:
            m = int(mes_filtro)
            yr = int(anio_filtro) if anio_filtro.isdigit() else today.year
            es_periodo_personalizado = True
            clave_tarjeta = (yr, m)
            card_etiqueta = f"{MESES_ES[m - 1]} {yr}"
        else:
            clave_tarjeta = (today.year, today.month)
            card_etiqueta = f"Este Mes ({MESES_ES[today.month - 1]} {today.year})"

        card_titulo = "Resumen Mensual"
        card_periodo_nombre = "del mes"
        periodo_display = "Mensual"

    else:  # anual
        if anio_filtro.isdigit():
            yr = int(anio_filtro)
            es_periodo_personalizado = True
            clave_tarjeta = (yr,)
            card_etiqueta = f"Año {yr}"
        else:
            clave_tarjeta = (today.year,)
            card_etiqueta = f"Este Año ({today.year})"

        card_titulo = "Resumen del Año"
        card_periodo_nombre = "del año"
        periodo_display = "Anual"

    # Datos específicos para las tarjetas grandes
    card_datos = resumen.get(clave_tarjeta, {
        'ninos': 0, 'ninos_45': 0, 'ninos_90': 0, 'ninos_renovados_45': 0,
        'fiestas': 0, 'brazaletes': 0, 'tiempo_fiestas': 0,
    })

    card_n45 = card_datos['ninos_45']
    card_n90 = card_datos['ninos_90']
    card_renovados = card_datos['ninos_renovados_45']
    card_n45_base = max(0, card_n45 - card_renovados)

    card_cash_45 = round(card_n45 * PRECIO_NINO_45, 2)
    card_cash_45_base = round(card_n45_base * PRECIO_NINO_45, 2)
    card_cash_90 = round(card_n90 * PRECIO_NINO_90, 2)
    card_cash_nuevos = round(card_renovados * PRECIO_NINO_45, 2)
    card_cash_total = round(card_cash_45 + card_cash_90, 2)

    card_f = card_datos['fiestas']
    card_br = card_datos['brazaletes']
    card_prom_f = round(card_datos['tiempo_fiestas'] / card_f, 1) if card_f else 0

    filas = []
    tot_ninos = tot_ninos_45 = tot_ninos_90 = tot_fiestas = tot_brazaletes = 0
    tot_ninos_renovados_45 = 0
    tot_tiempo_fiestas = 0
    tot_cash_45 = 0.0
    tot_cash_45_base = 0.0
    tot_cash_90 = 0.0
    tot_cash_nuevos = 0.0
    tot_cash_total = 0.0

    for clave in claves_ordenadas:
        datos = resumen[clave]
        n = datos['ninos']
        n45 = datos['ninos_45']
        n90 = datos['ninos_90']
        n_renovados = datos['ninos_renovados_45']
        f = datos['fiestas']
        br = datos['brazaletes']

        cash_45 = round(n45 * PRECIO_NINO_45, 2)
        cash_90 = round(n90 * PRECIO_NINO_90, 2)
        cash_nuevos = round(n_renovados * PRECIO_NINO_45, 2)
        cash_45_base = round(max(0, n45 - n_renovados) * PRECIO_NINO_45, 2)
        cash_total = round(cash_45 + cash_90, 2)

        etiqueta_periodo = _formatear_etiqueta_periodo(clave, periodo)
        es_seleccionada = (clave == clave_tarjeta)

        # Generar URL para ver directamente en los cuadros grandes
        if periodo == 'dia':
            f_iso = clave[3].strftime('%Y-%m-%d')
            url_ver = f"?periodo=dia&fecha={f_iso}"
            if anio_filtro: url_ver += f"&anio={anio_filtro}"
            if mes_filtro: url_ver += f"&mes={mes_filtro}"
        elif periodo == 'semanal':
            url_ver = f"?periodo=semanal&semana={clave[1]}&anio={clave[0]}"
            if mes_filtro: url_ver += f"&mes={mes_filtro}"
        elif periodo == 'mensual':
            url_ver = f"?periodo=mensual&mes={clave[1]}&anio={clave[0]}"
        else:
            url_ver = f"?periodo=anual&anio={clave[0]}"

        filas.append({
            'clave': clave,
            'etiqueta': etiqueta_periodo,
            'es_seleccionada': es_seleccionada,
            'url_ver': url_ver,
            'ninos': n,
            'ninos_45': n45,
            'ninos_90': n90,
            'ninos_renovados_45': n_renovados,
            'cash_45': cash_45,
            'cash_45_base': cash_45_base,
            'cash_90': cash_90,
            'cash_nuevos': cash_nuevos,
            'cash_total': cash_total,
            'fiestas': f,
            'brazaletes': br,
            'tiempo_prom_fiestas': round(datos['tiempo_fiestas'] / f, 1) if f else 0,
        })

        tot_ninos += n
        tot_ninos_45 += n45
        tot_ninos_90 += n90
        tot_ninos_renovados_45 += n_renovados
        tot_cash_45 += cash_45
        tot_cash_45_base += cash_45_base
        tot_cash_90 += cash_90
        tot_cash_nuevos += cash_nuevos
        tot_cash_total += cash_total
        tot_fiestas += f
        tot_brazaletes += br
        tot_tiempo_fiestas += datos['tiempo_fiestas']

    prom_fiestas = round(tot_tiempo_fiestas / tot_fiestas, 1) if tot_fiestas else 0

    return render(request, 'control_nino/estadisticas.html', {
        'filas': filas,
        'anios': anios,
        'anio': anio_filtro,
        'mes_filtro': mes_filtro,
        'fecha_filtro': fecha_filtro,
        'semana_filtro': semana_filtro,
        'meses_es': [{'num': i + 1, 'nombre': m} for i, m in enumerate(MESES_ES)],
        'periodo': periodo,
        'periodo_display': periodo_display,
        'card_titulo': card_titulo,
        'card_etiqueta': card_etiqueta,
        'card_periodo_nombre': card_periodo_nombre,
        'es_periodo_personalizado': es_periodo_personalizado,

        # Métricas para las tarjetas de resumen (periodo activo: día, semana, mes o año)
        'total_ninos': card_datos['ninos'],
        'total_ninos_45': card_n45,
        'total_ninos_45_base': card_n45_base,
        'total_ninos_90': card_n90,
        'total_ninos_renovados_45': card_renovados,
        'total_cash_45': card_cash_45,
        'total_cash_45_base': card_cash_45_base,
        'total_cash_90': card_cash_90,
        'total_cash_nuevos': card_cash_nuevos,
        'total_cash_total': card_cash_total,
        'total_fiestas': card_f,
        'total_brazaletes': card_br,
        'prom_fiestas': card_prom_f,

        # Totales para el pie de la tabla detallada
        'tabla_total_ninos': tot_ninos,
        'tabla_total_ninos_45': tot_ninos_45,
        'tabla_total_ninos_45_base': max(0, tot_ninos_45 - tot_ninos_renovados_45),
        'tabla_total_ninos_90': tot_ninos_90,
        'tabla_total_ninos_renovados_45': tot_ninos_renovados_45,
        'tabla_total_cash_45': round(tot_cash_45, 2),
        'tabla_total_cash_45_base': round(tot_cash_45_base, 2),
        'tabla_total_cash_90': round(tot_cash_90, 2),
        'tabla_total_cash_nuevos': round(tot_cash_nuevos, 2),
        'tabla_total_cash_total': round(tot_cash_total, 2),
        'tabla_total_fiestas': tot_fiestas,
        'tabla_total_brazaletes': tot_brazaletes,
        'tabla_prom_fiestas': prom_fiestas,

        'precio_45': PRECIO_NINO_45,
        'precio_90': PRECIO_NINO_90,
    })


def _obtener_clave_periodo(dt_local, periodo):
    """Devuelve una tupla como clave según la granularidad."""
    y = dt_local.year
    m = dt_local.month
    d = dt_local.date()

    if periodo == 'dia':
        return (y, m, d.day, d)
    elif periodo == 'semanal':
        # Lunes de la semana
        lunes = d - timedelta(days=d.weekday())
        domingo = lunes + timedelta(days=6)
        num_semana = d.isocalendar()[1]
        return (y, num_semana, lunes, domingo)
    elif periodo == 'anual':
        return (y,)
    else:  # mensual
        return (y, m)


def _sort_clave_periodo(clave, periodo):
    if periodo == 'dia':
        return clave[3]  # fecha date
    elif periodo == 'semanal':
        return clave[2]  # lunes date
    elif periodo == 'anual':
        return clave[0]
    else:  # mensual
        return (clave[0], clave[1])


def _formatear_etiqueta_periodo(clave, periodo):
    if periodo == 'dia':
        date_obj = clave[3]
        return date_obj.strftime('%d/%m/%Y')
    elif periodo == 'semanal':
        lunes, domingo = clave[2], clave[3]
        return f"Semana {clave[1]} ({lunes.strftime('%d/%m')} al {domingo.strftime('%d/%m/%Y')})"
    elif periodo == 'anual':
        return f"Año {clave[0]}"
    else:  # mensual
        nombre_mes = MESES_ES[clave[1] - 1]
        return f"{nombre_mes} {clave[0]}"


@login_required
@control_nino_required
def crear_fiesta(request):
    brazaletes_data = []
    if request.method == 'POST':
        form = FiestaForm(request.POST)
        nombres = request.POST.getlist('brazalete_nombre')
        descripciones = request.POST.getlist('brazalete_descripcion')

        if form.is_valid():
            try:
                with transaction.atomic():
                    fiesta = form.save()
                    cantidad = form.cleaned_data['cantidad_brazaletes']
                    BrazaleteFiesta.objects.bulk_create([
                        BrazaleteFiesta(
                            fiesta=fiesta,
                            numero=i + 1,
                            nombre=(nombres[i].strip() if i < len(nombres) and nombres[i].strip() else None),
                            descripcion=(descripciones[i].strip() if i < len(descripciones) and descripciones[i].strip() else None),
                        )
                        for i in range(cantidad)
                    ])
                messages.success(request, f"Fiesta '{fiesta.nombre}' creada con {cantidad} brazaletes.")
                if request.user.is_superuser or getattr(getattr(request.user, 'perfilusuario', None), 'rol', None) != 'control_nino':
                    return redirect('control_nino:detalle_fiesta', pk=fiesta.pk)
                return redirect('control_nino:lista_control_ninos')
            except Exception as e:
                messages.error(request, f"Error al crear la fiesta: {str(e)}")

        try:
            cantidad_int = int(request.POST.get('cantidad_brazaletes', ''))
        except (TypeError, ValueError):
            cantidad_int = 0
        brazaletes_data = [
            {
                'nombre': nombres[i] if i < len(nombres) else '',
                'descripcion': descripciones[i] if i < len(descripciones) else '',
            }
            for i in range(max(0, cantidad_int))
        ]
    else:
        form = FiestaForm()
    return render(request, 'control_nino/fiesta_form.html', {
        'form': form,
        'titulo': 'Agregar Fiesta',
        'brazaletes_data': brazaletes_data,
    })


@login_required
@control_nino_required
def editar_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta.objects.prefetch_related('brazaletes'), pk=pk)
    brazaletes_existentes = list(fiesta.brazaletes.all().order_by('numero'))
    
    if request.method == 'POST':
        # Guardar valores previos para detallar cambios en la novedad
        prev_nombre = fiesta.nombre
        prev_tiempo = fiesta.tiempo
        prev_cantidad = len(brazaletes_existentes)
        prev_brazaletes = {b.numero: (b.nombre or '', b.descripcion or '') for b in brazaletes_existentes}

        form = FiestaForm(request.POST, instance=fiesta)
        nombres = request.POST.getlist('brazalete_nombre')
        descripciones = request.POST.getlist('brazalete_descripcion')

        if form.is_valid():
            try:
                with transaction.atomic():
                    fiesta = form.save()
                    cantidad = form.cleaned_data['cantidad_brazaletes']
                    
                    # Actualizar existentes o crear nuevos
                    for i in range(cantidad):
                        nombre_val = nombres[i].strip() if i < len(nombres) and nombres[i].strip() else None
                        desc_val = descripciones[i].strip() if i < len(descripciones) and descripciones[i].strip() else None
                        numero_val = i + 1
                        
                        if i < len(brazaletes_existentes):
                            b = brazaletes_existentes[i]
                            b.numero = numero_val
                            b.nombre = nombre_val
                            b.descripcion = desc_val
                            b.save()
                        else:
                            BrazaleteFiesta.objects.create(
                                fiesta=fiesta,
                                numero=numero_val,
                                nombre=nombre_val,
                                descripcion=desc_val
                            )
                    
                    # Si se redujo la cantidad, eliminar los sobrantes
                    if len(brazaletes_existentes) > cantidad:
                        sobrantes_ids = [b.pk for b in brazaletes_existentes[cantidad:]]
                        BrazaleteFiesta.objects.filter(pk__in=sobrantes_ids).delete()

                    # Construir reporte detallado de cambios para la novedad
                    cambios = []
                    if prev_nombre != fiesta.nombre:
                        cambios.append(f"Nombre: '{prev_nombre}' ➜ '{fiesta.nombre}'")
                    if prev_tiempo != fiesta.tiempo:
                        cambios.append(f"Tiempo: {prev_tiempo} min ➜ {fiesta.tiempo} min")
                    if prev_cantidad != cantidad:
                        cambios.append(f"Cantidad de brazaletes: {prev_cantidad} ➜ {cantidad}")

                    braz_cambiados = []
                    for i in range(cantidad):
                        num = i + 1
                        n_act = (nombres[i].strip() if i < len(nombres) and nombres[i].strip() else '')
                        d_act = (descripciones[i].strip() if i < len(descripciones) and descripciones[i].strip() else '')
                        n_ant, d_ant = prev_brazaletes.get(num, ('', ''))
                        if num not in prev_brazaletes:
                            braz_cambiados.append(f"Brazalete #{num} añadido ('{n_act or 'Sin nombre'}')")
                        elif n_act != n_ant or d_act != d_ant:
                            braz_cambiados.append(f"Brazalete #{num}: '{n_ant}' ➜ '{n_act}'" + (f" (desc: '{d_ant}' ➜ '{d_act}')" if d_act != d_ant else ""))

                    if prev_cantidad > cantidad:
                        braz_cambiados.append(f"Se eliminaron {prev_cantidad - cantidad} brazaletes sobrantes")

                    if braz_cambiados:
                        cambios.append("Brazaletes: " + "; ".join(braz_cambiados))

                    desc_novedad = " | ".join(cambios) if cambios else "Se guardó la fiesta sin cambios en sus campos principales."
                    registrar_novedad_sistema(
                        titulo=f"Fiesta editada: {fiesta.nombre}",
                        descripcion=desc_novedad,
                        usuario=request.user,
                        fiesta=fiesta
                    )

                messages.success(request, f"Fiesta '{fiesta.nombre}' actualizada exitosamente.")
                return redirect('control_nino:lista_control_ninos')
            except Exception as e:
                messages.error(request, f"Error al actualizar la fiesta: {str(e)}")

        try:
            cantidad_int = int(request.POST.get('cantidad_brazaletes', len(brazaletes_existentes)))
        except (TypeError, ValueError):
            cantidad_int = len(brazaletes_existentes)
            
        brazaletes_data = [
            {
                'nombre': nombres[i] if i < len(nombres) else '',
                'descripcion': descripciones[i] if i < len(descripciones) else '',
            }
            for i in range(max(0, cantidad_int))
        ]
    else:
        form = FiestaForm(instance=fiesta, initial={'cantidad_brazaletes': len(brazaletes_existentes)})
        brazaletes_data = [
            {
                'nombre': b.nombre or '',
                'descripcion': b.descripcion or '',
            }
            for b in brazaletes_existentes
        ]

    return render(request, 'control_nino/fiesta_form.html', {
        'form': form,
        'titulo': f'Editar Fiesta: {fiesta.nombre}',
        'brazaletes_data': brazaletes_data,
        'es_edicion': True,
        'fiesta': fiesta,
    })


@login_required
@control_nino_required
@control_nino_gestion_required
def detalle_fiesta(request, pk):
    _finalizar_vencidos()
    fiesta = get_object_or_404(Fiesta.objects.prefetch_related('brazaletes'), pk=pk)
    return render(request, 'control_nino/fiesta_detalle.html', {
        'fiesta': fiesta,
        'ahora_ms': int(timezone.now().timestamp() * 1000),
        'tiempo_maximo': TIEMPO_MAXIMO,
    })


@login_required
@control_nino_required
def iniciar_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta, pk=pk)
    if request.method == 'POST' and not fiesta.iniciada:
        fiesta.hora_inicio = timezone.now()
        fiesta.save(update_fields=['hora_inicio'])
        messages.success(request, "El tiempo de la fiesta ha iniciado.")
    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect('control_nino:detalle_fiesta', pk=pk)


@login_required
@control_nino_required
def marcar_salida_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta, pk=pk)
    if request.method == 'POST':
        if not fiesta.hora_salida:
            fiesta.hora_salida = timezone.now()
            fiesta.save(update_fields=['hora_salida'])
            messages.success(request, f"Salida confirmada para la fiesta '{fiesta.nombre}'.")
        else:
            messages.info(request, f"La fiesta '{fiesta.nombre}' ya tenía salida confirmada.")
    return redirect('control_nino:lista_control_ninos')


@login_required
@control_nino_required
def deshacer_salida_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta, pk=pk)
    if request.method == 'POST':
        fiesta.hora_salida = None
        fiesta.save(update_fields=['hora_salida'])
        messages.success(request, f"Salida de la fiesta '{fiesta.nombre}' eliminada.")
    return redirect('control_nino:lista_control_ninos')


@login_required
@control_nino_required
def agregar_tiempo_fiesta(request, pk):
    """Suma 45 o 90 minutos al tiempo total de una fiesta, sin superar el máximo."""
    fiesta = get_object_or_404(Fiesta, pk=pk)
    es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'Método no permitido.'}, status=405) if es_ajax else redirect('control_nino:lista_control_ninos')

    try:
        minutos = int(request.POST.get('minutos', 0))
    except (TypeError, ValueError):
        minutos = 0

    error = None
    if minutos not in (45, 90):
        error = 'Solo se permiten 45 o 90 minutos.'
    elif fiesta.salio:
        error = 'La fiesta ya finalizó.'
    elif fiesta.tiempo >= TIEMPO_MAXIMO:
        error = f"La fiesta ya alcanzó el máximo de {TIEMPO_MAXIMO} minutos."
    elif fiesta.tiempo + minutos > TIEMPO_MAXIMO:
        error = f"No se pueden superar los {TIEMPO_MAXIMO} minutos en total."

    if error:
        if es_ajax:
            return JsonResponse({'ok': False, 'error': error, 'tiempo': fiesta.tiempo}, status=400)
        messages.error(request, error)
    else:
        tiempo_ant = fiesta.tiempo
        fiesta.tiempo += minutos
        fiesta.tiempo_adicional += minutos
        fiesta.save(update_fields=['tiempo', 'tiempo_adicional'])
        registrar_novedad_sistema(
            titulo=f"Tiempo añadido a fiesta: {fiesta.nombre}",
            descripcion=f"Se agregaron +{minutos} min a la fiesta '{fiesta.nombre}'. Tiempo anterior: {tiempo_ant} min ➜ Nuevo tiempo: {fiesta.tiempo} min.",
            usuario=request.user,
            fiesta=fiesta
        )
        if not es_ajax:
            messages.success(request, f"Se agregaron {minutos} minutos a la fiesta '{fiesta.nombre}'.")

    if es_ajax:
        return JsonResponse({'ok': error is None, 'tiempo': fiesta.tiempo, 'error': error})

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(next_url)
    return redirect('control_nino:lista_control_ninos')


@login_required
@control_nino_required
def eliminar_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta, pk=pk)
    if request.method == 'POST':
        nombre_fiesta = fiesta.nombre
        fiesta.delete()
        messages.success(request, "Fiesta eliminada.")
        return redirect('control_nino:lista_control_ninos')
    return render(request, 'control_nino/fiesta_eliminar.html', {'fiesta': fiesta})


@login_required
@control_nino_required
def lista_novedades(request):
    """Listado de novedades/bitácora del área de control de niños y fiestas."""
    tipo_filtro = request.GET.get('tipo', '').strip()
    q = request.GET.get('q', '').strip()
    fecha_str = request.GET.get('fecha', '').strip()

    novedades_qs = Novedad.objects.select_related('usuario', 'nino', 'fiesta').all()

    if tipo_filtro in ('SISTEMA', 'MANUAL', 'INCIDENTE'):
        novedades_qs = novedades_qs.filter(tipo=tipo_filtro)

    if q:
        from django.db.models import Q
        novedades_qs = novedades_qs.filter(
            Q(titulo__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(nino__nombre__icontains=q) |
            Q(fiesta__nombre__icontains=q) |
            Q(usuario__username__icontains=q)
        )

    if fecha_str:
        try:
            fecha_filtro = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            ini_f, fin_f = _rango_dia(fecha_filtro)
            novedades_qs = novedades_qs.filter(fecha_registro__gte=ini_f, fecha_registro__lt=fin_f)
        except ValueError:
            pass

    paginator = Paginator(novedades_qs, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'control_nino/novedades/lista.html', {
        'page_obj': page_obj,
        'tipo_filtro': tipo_filtro,
        'q': q,
        'fecha_str': fecha_str,
    })


@login_required
@control_nino_required
def crear_novedad_manual(request):
    """Las novedades se generan automáticamente por el sistema; redirige a la bitácora."""
    return redirect('control_nino:lista_novedades')
