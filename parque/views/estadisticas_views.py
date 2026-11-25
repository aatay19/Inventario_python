from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from ..models import DetalleEvento, Evento

MESES_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

PERIODOS = ('dia', 'semanal', 'mensual', 'anual')
ZONAS = {
    'PULPO': 'pulpo',
    'PARED_BLANCA': 'pared_blanca',
    'VENTANA': 'ventana',
}


def _resumen_vacio():
    return {
        'eventos': 0,
        'pulpo': 0,
        'pared_blanca': 0,
        'ventana': 0,
        'productos': 0,
        'combos': 0,
        'recaudado': Decimal('0'),
        'recaudado_bs': Decimal('0'),
    }


def _clave_periodo(fecha, periodo):
    """Agrupa una fecha de reserva según la granularidad elegida."""
    if isinstance(fecha, datetime):
        fecha = fecha.date()

    if periodo == 'dia':
        return (fecha.year, fecha.month, fecha.day, fecha)
    if periodo == 'semanal':
        lunes = fecha - timedelta(days=fecha.weekday())
        iso = lunes.isocalendar()
        return (iso[0], iso[1], lunes, lunes + timedelta(days=6))
    if periodo == 'anual':
        return (fecha.year,)
    return (fecha.year, fecha.month)


def _orden_periodo(clave, periodo):
    if periodo == 'dia':
        return clave[3]
    if periodo == 'semanal':
        return clave[2]
    return tuple(clave)


def _etiqueta_periodo(clave, periodo):
    if periodo == 'dia':
        return clave[3].strftime('%d/%m/%Y')
    if periodo == 'semanal':
        return f"Semana {clave[1]} ({clave[2].strftime('%d/%m')} al {clave[3].strftime('%d/%m/%Y')})"
    if periodo == 'anual':
        return f"Año {clave[0]}"
    return f"{MESES_ES[clave[1] - 1]} {clave[0]}"


def _parse_fecha(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _resumen_por_periodo(periodo):
    """Construye las métricas del parque a partir de eventos y sus ítems."""
    resumen = defaultdict(_resumen_vacio)
    anios = set()

    campos = (
        'fecha_inicio', 'zona', 'monto_abono1', 'tasa_dia',
        'monto_abono2', 'tasa_dia2',
    )
    for fecha, zona, abono1, tasa1, abono2, tasa2 in Evento.objects.values_list(*campos).iterator():
        if not fecha:
            continue
        anios.add(fecha.year)
        datos = resumen[_clave_periodo(fecha, periodo)]
        datos['eventos'] += 1

        clave_zona = ZONAS.get(zona)
        if clave_zona:
            datos[clave_zona] += 1

        if abono1:
            datos['recaudado'] += abono1
            if tasa1:
                datos['recaudado_bs'] += abono1 * tasa1
        if abono2:
            datos['recaudado'] += abono2
            if tasa2:
                datos['recaudado_bs'] += abono2 * tasa2

    items = DetalleEvento.objects.values_list(
        'evento__fecha_inicio', 'tipo_item', 'cantidad'
    ).iterator()
    for fecha, tipo, cantidad in items:
        if not fecha:
            continue
        datos = resumen[_clave_periodo(fecha, periodo)]
        if tipo == 'PRODUCTO':
            datos['productos'] += cantidad or 0
        elif tipo == 'COMBO':
            datos['combos'] += cantidad or 0

    return resumen, sorted(anios, reverse=True)


def _filtrar_claves(claves, anio, mes, fecha, semana, periodo):
    fecha_obj = _parse_fecha(fecha)
    resultado = []
    for clave in claves:
        if anio.isdigit() and clave[0] != int(anio):
            continue
        if mes.isdigit() and periodo in ('dia', 'semanal', 'mensual'):
            if periodo in ('dia', 'mensual') and clave[1] != int(mes):
                continue
            if periodo == 'semanal' and clave[2].month != int(mes) and clave[3].month != int(mes):
                continue
        if periodo == 'dia' and fecha_obj and clave[3] != fecha_obj:
            continue
        if periodo == 'semanal' and semana.isdigit() and clave[1] != int(semana):
            continue
        resultado.append(clave)
    return resultado


def _clave_y_etiqueta_activa(periodo, anio, mes, fecha, semana, hoy, claves):
    """Periodo que muestran las tarjetas grandes."""
    personalizado = False
    tiene_filtros = bool(anio or mes or fecha or semana)

    if periodo == 'dia':
        fecha_obj = _parse_fecha(fecha)
        if fecha_obj:
            personalizado = True
        else:
            fecha_obj = hoy
        clave = _clave_periodo(fecha_obj, 'dia')
        titulo = 'Resumen del Día'
        nombre = 'del día'
        display = 'Por Día'
        if fecha_obj == hoy and not personalizado:
            etiqueta = f"Hoy ({hoy.strftime('%d/%m/%Y')})"
        else:
            etiqueta = fecha_obj.strftime('%d/%m/%Y')

    elif periodo == 'semanal':
        if semana.isdigit() and 1 <= int(semana) <= 53:
            anio_ref = int(anio) if anio.isdigit() else hoy.isocalendar()[0]
            try:
                lunes = date.fromisocalendar(anio_ref, int(semana), 1)
            except ValueError:
                lunes = hoy - timedelta(days=hoy.weekday())
            clave = _clave_periodo(lunes, 'semanal')
            personalizado = True
        else:
            lunes = hoy - timedelta(days=hoy.weekday())
            clave = _clave_periodo(lunes, 'semanal')
        etiqueta = (
            f"Semana {clave[1]} "
            f"({clave[2].strftime('%d/%m')} al {clave[3].strftime('%d/%m/%Y')})"
        )
        titulo = 'Resumen Semanal'
        nombre = 'de la semana'
        display = 'Semanal'

    elif periodo == 'mensual':
        if mes.isdigit() and 1 <= int(mes) <= 12:
            anio_ref = int(anio) if anio.isdigit() else hoy.year
            clave = (anio_ref, int(mes))
            etiqueta = f"{MESES_ES[int(mes) - 1]} {anio_ref}"
            personalizado = True
        else:
            clave = (hoy.year, hoy.month)
            etiqueta = f"Este Mes ({MESES_ES[hoy.month - 1]} {hoy.year})"
        titulo = 'Resumen Mensual'
        nombre = 'del mes'
        display = 'Mensual'

    else:
        if anio.isdigit():
            clave = (int(anio),)
            etiqueta = f"Año {anio}"
            personalizado = True
        else:
            clave = (hoy.year,)
            etiqueta = f"Este Año ({hoy.year})"
        titulo = 'Resumen del Año'
        nombre = 'del año'
        display = 'Anual'

    # Sin filtros explícitos, si el periodo actual no tiene datos, mostrar el
    # periodo más reciente que sí los tenga para que los cuadros no queden en 0.
    if not tiene_filtros and claves and clave not in claves:
        clave = max(claves, key=lambda item: _orden_periodo(item, periodo))
        etiqueta = _etiqueta_periodo(clave, periodo)

    return clave, etiqueta, titulo, nombre, display, personalizado


def _url_periodo(clave, periodo):
    if periodo == 'dia':
        return f"?periodo=dia&fecha={clave[3].strftime('%Y-%m-%d')}"
    if periodo == 'semanal':
        return f"?periodo=semanal&anio={clave[0]}&semana={clave[1]}"
    if periodo == 'mensual':
        return f"?periodo=mensual&anio={clave[0]}&mes={clave[1]}"
    return f"?periodo=anual&anio={clave[0]}"


@login_required
def estadisticas_parque(request):
    """Estadísticas del parque: eventos, zonas, ítems y recaudación por periodo."""
    perfil = getattr(request.user, 'perfilusuario', None)
    if not perfil or perfil.rol.lower() not in ('soporte', 'parque', 'admin'):
        messages.error(request, "No tienes permisos para acceder a la sección del Parque.")
        return redirect('index')

    periodo = request.GET.get('periodo', 'mensual').strip().lower()
    if periodo not in PERIODOS:
        periodo = 'mensual'

    anio = request.GET.get('anio', '').strip()
    mes = request.GET.get('mes', '').strip()
    fecha = request.GET.get('fecha', '').strip()
    semana = request.GET.get('semana', '').strip()

    hoy = timezone.localdate()
    resumen, anios = _resumen_por_periodo(periodo)
    claves_filtradas = _filtrar_claves(resumen.keys(), anio, mes, fecha, semana, periodo)
    claves_ordenadas = sorted(claves_filtradas, key=lambda c: _orden_periodo(c, periodo), reverse=True)

    clave_activa, etiqueta, titulo, nombre, display, personalizado = _clave_y_etiqueta_activa(
        periodo, anio, mes, fecha, semana, hoy, claves_filtradas
    )
    card = resumen.get(clave_activa, _resumen_vacio())

    filas = []
    totales = _resumen_vacio()
    for clave in claves_ordenadas:
        datos = resumen[clave]
        filas.append({
            'etiqueta': _etiqueta_periodo(clave, periodo),
            'es_activa': clave == clave_activa,
            'url_ver': _url_periodo(clave, periodo),
            'eventos': datos['eventos'],
            'pulpo': datos['pulpo'],
            'pared_blanca': datos['pared_blanca'],
            'ventana': datos['ventana'],
            'productos': datos['productos'],
            'combos': datos['combos'],
            'recaudado': datos['recaudado'],
            'recaudado_bs': datos['recaudado_bs'],
        })
        for campo in totales:
            totales[campo] += datos[campo]

    return render(request, 'parque/estadisticas.html', {
        'filas': filas,
        'anios': anios,
        'anio': anio,
        'mes': mes,
        'fecha': fecha,
        'semana': semana,
        'meses_es': [{'num': i + 1, 'nombre': nombre_mes} for i, nombre_mes in enumerate(MESES_ES)],
        'periodo': periodo,
        'periodo_display': display,
        'card_titulo': titulo,
        'card_etiqueta': etiqueta,
        'card_periodo_nombre': nombre,
        'es_periodo_personalizado': personalizado,

        'total_eventos': card['eventos'],
        'total_pulpo': card['pulpo'],
        'total_pared_blanca': card['pared_blanca'],
        'total_ventana': card['ventana'],
        'total_productos': card['productos'],
        'total_combos': card['combos'],
        'total_recaudado': card['recaudado'],
        'total_recaudado_bs': card['recaudado_bs'],

        'tabla_totales': totales,
    })
