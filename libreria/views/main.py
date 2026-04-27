import io
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, F, Sum
from django.utils import timezone
from django.http import HttpResponse
from django.core.management import call_command
from .auth import es_admin
from ..models import Proveedor, Inventario, MovimientosInventario
from datetime import timedelta

@login_required
def index(request):
    if hasattr(request.user, 'perfilusuario') and request.user.perfilusuario.rol == 'consulta':
        if not request.session.get('consulta_redirected'):
            request.session['consulta_redirected'] = True
            return redirect('movimientos.index')

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
    if hasattr(request.user, 'perfilusuario') and request.user.perfilusuario.rol.lower() == 'consulta':
        cantidad_movs = 10
        
    ultimos_movimientos = MovimientosInventario.objects.exclude(tipo_movimiento='PEDIDO').select_related('producto', 'proveedor').order_by('-fecha_movimiento')[:cantidad_movs]

    productos_bajo_stock = Inventario.objects.filter(
        cantidad__lte=F('stock_minimo')
    ).values('nombre_producto', 'cantidad', 'stock_minimo')

    hace_30_dias = timezone.now() - timedelta(days=30)
    
    mayor_rotacion = MovimientosInventario.objects.filter(
        tipo_movimiento='SALIDA',
        fecha_movimiento__gte=hace_30_dias
    ).values('producto__nombre_producto').annotate(
        total=Sum('cantidad')
    ).order_by('-total')[:5]

    menor_rotacion = Inventario.objects.annotate(
        total_salidas=Sum(
            'movimientosinventario__cantidad',
            filter=Q(movimientosinventario__tipo_movimiento='SALIDA') & 
                   Q(movimientosinventario__fecha_movimiento__gte=hace_30_dias)
        )
    ).filter(cantidad__gt=0).order_by('total_salidas', '-cantidad')[:5]

    context = {
        'producto_top': producto_top,
        'ultimos_movimientos': ultimos_movimientos,
        'productos_bajo_stock': productos_bajo_stock,
        'num_bajo_stock': productos_bajo_stock.count(),
        'mayor_rotacion': mayor_rotacion,
        'menor_rotacion': menor_rotacion,
    }

    return render(request, 'index.html', context)

@login_required
@user_passes_test(es_admin, login_url='index')
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
