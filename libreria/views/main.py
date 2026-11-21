import io
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, F, Sum
from django.utils import timezone
from django.http import HttpResponse
from django.core.management import call_command
from .auth import es_soporte_gestion
from ..models import Proveedor, Inventario, MovimientosInventario
from datetime import timedelta

@login_required
def hub(request):
    """Vista principal de bienvenida: muestra las secciones disponibles según el rol del usuario."""
    perfil = getattr(request.user, 'perfilusuario', None)
    rol = perfil.rol.lower() if perfil else ''

    # Todos los usuarios entran al hub; solo se filtran las tarjetas de las
    # secciones a las que tienen acceso.
    ROLES_PARQUE    = {'admin', 'soporte', 'parque'}
    ROLES_NINO      = {'admin', 'soporte', 'control_nino'}
    ROLES_CAJA      = {'admin', 'soporte', 'supervisor_caja', 'cuadre_caja', 'supervisor_cuadre_caja'}
    ROLES_INV       = {'admin', 'soporte', 'almacenista', 'inventario', 'supervisor_inventario'}

    secciones = []

    if rol in ROLES_INV or not rol:
        secciones.append({
            'nombre': 'Control Inventario',
            'descripcion': 'Gestión de productos, movimientos, compras y proveedores.',
            'url_name': 'index',
            'icono': 'bi-boxes',
            'color': 'primary',
            'gradiente': 'linear-gradient(135deg, #1a73e8, #0d47a1)',
        })

    if rol in ROLES_NINO or not rol:
        secciones.append({
            'nombre': 'Control Niño',
            'descripcion': 'Registro de niños, control de tiempo y reportes de fiestas.',
            'url_name': 'control_nino:lista_control_ninos',
            'icono': 'bi-balloon-fill',
            'color': 'success',
            'gradiente': 'linear-gradient(135deg, #34a853, #1b5e20)',
        })

    if rol in ROLES_CAJA or not rol:
        secciones.append({
            'nombre': 'Cuadre de Caja',
            'descripcion': 'Gestión de turnos, ingresos, egresos y cierre de caja.',
            'url_name': 'cuadre_caja:index',
            'icono': 'bi-cash-coin',
            'color': 'warning',
            'gradiente': 'linear-gradient(135deg, #fbbc04, #e37400)',
        })

    if rol in ROLES_PARQUE or not rol:
        secciones.append({
            'nombre': 'Control Parque',
            'descripcion': 'Reservas de eventos, abonos, productos y brazaletes del parque.',
            'url_name': 'parque:calendario',
            'icono': 'bi-tree-fill',
            'color': 'danger',
            'gradiente': 'linear-gradient(135deg, #ea4335, #b71c1c)',
        })

    return render(request, 'hub.html', {
        'secciones': secciones,
        'nombre_usuario': request.user.first_name or request.user.username,
    })


@login_required
def index(request):
    perfil = getattr(request.user, 'perfilusuario', None)
    rol = perfil.rol.lower() if perfil else None

    if rol == 'almacenista':
        return redirect('movimientos.entrada')

    # Los roles exclusivos de caja solo ven el módulo de Cuadre de Caja.
    if rol in {'supervisor_caja', 'cuadre_caja'}:
        return redirect('cuadre_caja:index')

    total_proveedores = Proveedor.objects.count()
    total_productos = Inventario.objects.count()

    pm = MovimientosInventario.objects.exclude(tipo_movimiento='PEDIDO').values(
        'producto__nombre_producto',
        'producto__stock_minimo',
        'producto__stock_maximo',
        'producto__cantidad'
    ).annotate(
        total_movimientos=Sum('cantidad')
    ).order_by('-total_movimientos').first()

    producto_top = {
        'nombre': pm['producto__nombre_producto'] if pm else "N/A",
        'total': pm['total_movimientos'] if pm else 0,
        'min': pm['producto__stock_minimo'] if pm else 0,
        'max': pm['producto__stock_maximo'] if pm else 0,
        'stock': pm['producto__cantidad'] if pm else 0,
    }

    cantidad_movs = 5
    ultimos_movimientos = MovimientosInventario.objects.exclude(tipo_movimiento='PEDIDO').select_related('producto', 'proveedor').order_by('-fecha_movimiento')[:cantidad_movs]

    productos_bajo_stock = Inventario.objects.filter(
        cantidad__lte=F('stock_minimo')
    ).values('nombre_producto', 'cantidad', 'stock_minimo')

    hace_6_dias = timezone.now() - timedelta(days=6)
    
    mayor_rotacion = MovimientosInventario.objects.filter(
        tipo_movimiento='SALIDA',
        fecha_movimiento__gte=hace_6_dias
    ).values('producto__nombre_producto').annotate(
        total=Sum('cantidad')
    ).order_by('-total')[:5]

    menor_rotacion = Inventario.objects.annotate(
        total_salidas=Sum(
            'movimientosinventario__cantidad',
            filter=Q(movimientosinventario__tipo_movimiento='SALIDA') & 
                   Q(movimientosinventario__fecha_movimiento__gte=hace_6_dias)
        )
    ).filter(cantidad__gt=0).order_by('total_salidas', '-cantidad')[:5]

    productos_mayor_movimiento = MovimientosInventario.objects.exclude(tipo_movimiento='PEDIDO').values(
        'producto__nombre_producto',
        'producto__codigo_producto'
    ).annotate(
        total_entradas=Sum('cantidad', filter=Q(tipo_movimiento='ENTRADA')),
        total_salidas=Sum('cantidad', filter=Q(tipo_movimiento='SALIDA')),
        total_movimientos=Sum('cantidad')
    ).order_by('-total_movimientos')[:15]

    context = {
        'producto_top': producto_top,
        'ultimos_movimientos': ultimos_movimientos,
        'productos_bajo_stock': productos_bajo_stock,
        'num_bajo_stock': productos_bajo_stock.count(),
        'mayor_rotacion': mayor_rotacion,
        'menor_rotacion': menor_rotacion,
        'productos_mayor_movimiento': productos_mayor_movimiento,
    }

    return render(request, 'index.html', context)

from django.http import JsonResponse

@login_required
@user_passes_test(es_soporte_gestion, login_url='index')
def realizar_copia_seguridad(request):
    output = io.StringIO()
    modelos_a_incluir = [
        'libreria.Proveedor',
        'libreria.Inventario',
        'libreria.MovimientosInventario',
        'libreria.HistorialProveedoresNotas',
    ]
    call_command('dumpdata', *modelos_a_incluir, stdout=output)
    response = HttpResponse(output.getvalue(), content_type='application/json')
    filename = f"backup_inventario_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def api_mayor_movimiento(request):
    q = request.GET.get('q', '').strip()
    sort_by = request.GET.get('sort', 'total_desc')

    qs = MovimientosInventario.objects.exclude(tipo_movimiento='PEDIDO').values(
        'producto__nombre_producto',
        'producto__codigo_producto'
    ).annotate(
        total_entradas=Sum('cantidad', filter=Q(tipo_movimiento='ENTRADA')),
        total_salidas=Sum('cantidad', filter=Q(tipo_movimiento='SALIDA')),
        total_movimientos=Sum('cantidad')
    )

    if q:
        qs = qs.filter(
            Q(producto__nombre_producto__icontains=q) |
            Q(producto__codigo_producto__icontains=q)
        )

    if sort_by == 'entradas_desc':
        qs = qs.order_by('-total_entradas')
    elif sort_by == 'entradas_asc':
        qs = qs.order_by('total_entradas')
    elif sort_by == 'salidas_desc':
        qs = qs.order_by('-total_salidas')
    elif sort_by == 'salidas_asc':
        qs = qs.order_by('total_salidas')
    elif sort_by == 'total_asc':
        qs = qs.order_by('total_movimientos')
    else:
        qs = qs.order_by('-total_movimientos')
        
    qs = qs[:50]

    data = []
    for item in qs:
        data.append({
            'codigo': item['producto__codigo_producto'],
            'nombre': item['producto__nombre_producto'],
            'entradas': item['total_entradas'] or 0,
            'salidas': item['total_salidas'] or 0,
            'total': item['total_movimientos'] or 0
        })

    return JsonResponse({'success': True, 'data': data})
