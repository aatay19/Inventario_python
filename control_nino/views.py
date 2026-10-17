from collections import defaultdict
from datetime import datetime, time, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from fpdf import FPDF

from .models import ControlNino, Fiesta, BrazaleteFiesta
from .forms import ControlNinoForm, FiestaForm
from .permissions import control_nino_required


def _rango_dia(dia):
    """Devuelve el rango [inicio, fin) con zona horaria para un día dado."""
    inicio = timezone.make_aware(datetime.combine(dia, time.min))
    return inicio, inicio + timedelta(days=1)


@login_required
@control_nino_required
def lista_control_ninos(request):
    """Página principal: solo lo del día de hoy (se limpia sola cada día)."""
    hoy = timezone.localdate()
    inicio, fin = _rango_dia(hoy)
    ahora = timezone.now()

    ninos = ControlNino.objects.filter(
        fecha_registro__gte=inicio, fecha_registro__lt=fin
    ).order_by('fecha_registro')
    fiestas = Fiesta.objects.filter(
        fecha_registro__gte=inicio, fecha_registro__lt=fin
    ).order_by('-fecha_registro')

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
    })


@login_required
@control_nino_required
def crear_control_nino(request):
    if request.method == 'POST':
        form = ControlNinoForm(request.POST)
        if form.is_valid():
            nino = form.save()
            messages.success(request, f"Niño '{nino.nombre}' registrado con {nino.tiempo} minutos.")
            return redirect('control_nino:lista_control_ninos')
    else:
        form = ControlNinoForm()
    return render(request, 'control_nino/form.html', {'form': form, 'titulo': 'Agregar Niño'})


@login_required
@control_nino_required
def eliminar_control_nino(request, pk):
    nino = get_object_or_404(ControlNino, pk=pk)
    if request.method == 'POST':
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
def reporte_control_ninos(request):
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
def reporte_control_ninos_pdf(request):
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
    pdf.cell(190, 8, txt=f"Total de registros: {ninos.count()}", ln=True)

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
def reporte_control_nino_pdf(request, pk):
    """Reporte PDF individual de un niño."""
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
def reporte_fiesta_pdf(request, pk):
    """Reporte PDF individual de una fiesta con su lista de brazaletes."""
    fiesta = get_object_or_404(Fiesta, pk=pk)

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
def historial_control_ninos(request):
    """Historial de niños y fiestas agrupado por día."""
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

    dias = set()
    for dt in ninos_qs.values_list('fecha_registro', flat=True):
        dias.add(timezone.localtime(dt).date())
    for dt in fiestas_qs.values_list('fecha_registro', flat=True):
        dias.add(timezone.localtime(dt).date())

    dias = sorted(dias, reverse=True)
    paginator = Paginator(dias, 10)
    page = paginator.get_page(request.GET.get('page'))

    dias_data = []
    for dia in page.object_list:
        inicio, fin = _rango_dia(dia)
        ninos = ControlNino.objects.filter(
            fecha_registro__gte=inicio, fecha_registro__lt=fin
        ).order_by('fecha_registro')
        fiestas = Fiesta.objects.filter(
            fecha_registro__gte=inicio, fecha_registro__lt=fin
        ).order_by('-fecha_registro')
        dias_data.append({
            'fecha': dia,
            'ninos': ninos,
            'fiestas': fiestas,
            'total_ninos': ninos.count(),
            'total_fiestas': fiestas.count(),
            'total_brazaletes': BrazaleteFiesta.objects.filter(fiesta__in=fiestas).count(),
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


@login_required
@control_nino_required
def estadisticas_control_ninos(request):
    """Estadísticas mensuales: niños, fiestas y brazaletes por mes."""
    anio = request.GET.get('anio', '').strip()

    resumen = defaultdict(lambda: {
        'ninos': 0, 'ninos_45': 0, 'ninos_90': 0,
        'fiestas': 0, 'brazaletes': 0, 'tiempo_fiestas': 0,
    })

    for dt, tiempo in ControlNino.objects.values_list('fecha_registro', 'tiempo'):
        if dt:
            local = timezone.localtime(dt)
            datos = resumen[(local.year, local.month)]
            datos['ninos'] += 1
            if tiempo == 45:
                datos['ninos_45'] += 1
            elif tiempo == 90:
                datos['ninos_90'] += 1

    for dt, tiempo in Fiesta.objects.values_list('fecha_registro', 'tiempo'):
        if dt:
            local = timezone.localtime(dt)
            datos = resumen[(local.year, local.month)]
            datos['fiestas'] += 1
            datos['tiempo_fiestas'] += tiempo or 0

    for dt in BrazaleteFiesta.objects.values_list('fiesta__fecha_registro', flat=True):
        if dt:
            local = timezone.localtime(dt)
            resumen[(local.year, local.month)]['brazaletes'] += 1

    anios = sorted({clave[0] for clave in resumen}, reverse=True)

    if anio.isdigit():
        claves = [k for k in resumen if k[0] == int(anio)]
    else:
        claves = list(resumen)

    filas = []
    tot_ninos = tot_ninos_45 = tot_ninos_90 = tot_fiestas = tot_brazaletes = 0
    tot_tiempo_fiestas = 0
    for clave in sorted(claves, reverse=True):
        datos = resumen[clave]
        n = datos['ninos']
        f = datos['fiestas']
        filas.append({
            'anio': clave[0],
            'mes_num': clave[1],
            'mes': MESES_ES[clave[1] - 1],
            'ninos': n,
            'ninos_45': datos['ninos_45'],
            'ninos_90': datos['ninos_90'],
            'fiestas': f,
            'brazaletes': datos['brazaletes'],
            'tiempo_prom_fiestas': round(datos['tiempo_fiestas'] / f, 1) if f else 0,
        })
        tot_ninos += n
        tot_ninos_45 += datos['ninos_45']
        tot_ninos_90 += datos['ninos_90']
        tot_fiestas += f
        tot_brazaletes += datos['brazaletes']
        tot_tiempo_fiestas += datos['tiempo_fiestas']

    prom_fiestas = round(tot_tiempo_fiestas / tot_fiestas, 1) if tot_fiestas else 0

    return render(request, 'control_nino/estadisticas.html', {
        'filas': filas,
        'anios': anios,
        'anio': anio,
        'total_ninos': tot_ninos,
        'total_ninos_45': tot_ninos_45,
        'total_ninos_90': tot_ninos_90,
        'total_fiestas': tot_fiestas,
        'total_brazaletes': tot_brazaletes,
        'prom_fiestas': prom_fiestas,
    })


@login_required
@control_nino_required
def crear_fiesta(request):
    if request.method == 'POST':
        form = FiestaForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    fiesta = form.save()
                    cantidad = form.cleaned_data['cantidad_brazaletes']
                    BrazaleteFiesta.objects.bulk_create([
                        BrazaleteFiesta(fiesta=fiesta, numero=i)
                        for i in range(1, cantidad + 1)
                    ])
                messages.success(request, f"Fiesta '{fiesta.nombre}' creada con {cantidad} brazaletes.")
                return redirect('control_nino:detalle_fiesta', pk=fiesta.pk)
            except Exception as e:
                messages.error(request, f"Error al crear la fiesta: {str(e)}")
    else:
        form = FiestaForm()
    return render(request, 'control_nino/fiesta_form.html', {'form': form, 'titulo': 'Agregar Fiesta'})


@login_required
@control_nino_required
def detalle_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta, pk=pk)
    return render(request, 'control_nino/fiesta_detalle.html', {
        'fiesta': fiesta,
        'ahora_ms': int(timezone.now().timestamp() * 1000),
    })


@login_required
@control_nino_required
def iniciar_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta, pk=pk)
    if request.method == 'POST' and not fiesta.iniciada:
        fiesta.hora_inicio = timezone.now()
        fiesta.save(update_fields=['hora_inicio'])
        messages.success(request, "El tiempo de la fiesta ha iniciado.")
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
def eliminar_fiesta(request, pk):
    fiesta = get_object_or_404(Fiesta, pk=pk)
    if request.method == 'POST':
        fiesta.delete()
        messages.success(request, "Fiesta eliminada.")
        return redirect('control_nino:lista_control_ninos')
    return render(request, 'control_nino/fiesta_eliminar.html', {'fiesta': fiesta})
