from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Cliente, Proveedor, Inventario, HistorialProveedoresNotas,MovimientosInventario
from .forms import ClienteForm,ProveedorForm,InventarioForm,HistorialProveedoresNotasForm, MovimientosInventarioForm
from django.core.paginator import Paginator
from django.db.models import Q, F, Sum, Count, Value
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
from django.shortcuts import get_object_or_404
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image
from pyzbar.pyzbar import decode
# Create your views here.
# libreria/views.py
 
import json

# En tu archivo views.py (ejemplo de la lógica actual)
from django.db.models import Count
# ...

def index(request):
    # --- CÁLCULO PARA LAS TARJETAS (CARDS) ---

    # 1. Total de proveedores
    total_proveedores = Proveedor.objects.count()

    # 2. Total de productos
    total_productos = Inventario.objects.count()

    # 3. Valor total del inventario (usando 'cantidad' y 'precio_venta' de tu modelo)
    valor_inventario = Inventario.objects.aggregate(
        total=Sum(F('cantidad') * F('precio_venta'))
    )['total'] or 0

    # 4. Producto más vendido (basado en MovimientosInventario de tipo 'SALIDA')
    producto_mas_vendido = MovimientosInventario.objects.filter(
        tipo_movimiento='SALIDA'
    ).values('producto__nombre_producto').annotate(
        total_vendido=Sum('cantidad')
    ).order_by('-total_vendido').first()

    producto_top = {
        'nombre': producto_mas_vendido['producto__nombre_producto'] if producto_mas_vendido else "N/A",
        'total': producto_mas_vendido['total_vendido'] if producto_mas_vendido else 0
    }

    # --- DATOS PARA TABLAS Y GRÁFICAS ---

    # 5. Datos para la tabla: Top 5 productos más vendidos
    top_5_productos_vendidos = MovimientosInventario.objects.filter(
        tipo_movimiento='SALIDA'
    ).values('producto__nombre_producto').annotate(
        total_vendido=Sum('cantidad')
    ).order_by('-total_vendido')[:5]
    
    # Adaptamos la consulta para que coincida con lo que espera el template: {'nombre': ..., 'total_vendido': ...}
    top_productos = [{'nombre': item['producto__nombre_producto'], 'total_vendido': item['total_vendido']} for item in top_5_productos_vendidos]

    # 6. Gráfica de dona: Distribución de productos por categoría
    # Obtenemos los nombres legibles de las categorías desde el modelo
    categoria_display_map = dict(Inventario._meta.get_field('categoria').choices)

    distribucion_inventario = Inventario.objects.values('categoria').annotate(
        num_productos=Count('id_producto')
    ).filter(num_productos__gt=0).order_by('-num_productos')

    # Usamos el mapa para obtener el nombre legible. Si no lo encuentra, usa el original.
    labels_categorias = [
        categoria_display_map.get(item['categoria'], item['categoria']) for item in distribucion_inventario
    ]
    values_categorias = [item['num_productos'] for item in distribucion_inventario]

    # 7. Datos para la tabla de inventario por categoría
    # Reutilizamos la consulta anterior y la adaptamos para la tabla
    inventario_por_categoria = []
    for item in distribucion_inventario:
        inventario_por_categoria.append({
            'nombre': categoria_display_map.get(item['categoria'], item['categoria']),
            'num_productos': item['num_productos']
        })

    # 8. Datos para la tabla de resumen de movimientos
    # Para evitar problemas de zona horaria, definimos 'hoy' como un rango de tiempo.
    # Obtenemos la fecha actual en la zona horaria local del proyecto.
    local_today = timezone.localtime(timezone.now()).date()
    
    # Creamos un rango desde el inicio del día (00:00:00) hasta el final (23:59:59.999999).
    # Esto asegura que la consulta a la base de datos sea precisa.
    start_of_day = timezone.make_aware(datetime.combine(local_today, datetime.min.time()))
    end_of_day = timezone.make_aware(datetime.combine(local_today, datetime.max.time()))
    
    # Agregamos para obtener un resumen de movimientos
    resumen_movimientos = MovimientosInventario.objects.aggregate(
        total_entradas=Count('id_movimiento', filter=Q(tipo_movimiento='ENTRADA')),
        total_salidas=Count('id_movimiento', filter=Q(tipo_movimiento='SALIDA')),
        hoy_entradas=Count('id_movimiento', filter=Q(tipo_movimiento='ENTRADA', fecha_movimiento__range=(start_of_day, end_of_day))),
        hoy_salidas=Count('id_movimiento', filter=Q(tipo_movimiento='SALIDA', fecha_movimiento__range=(start_of_day, end_of_day))),
    )
    # Si no hay movimientos, los valores serán 0, lo cual es correcto.
    # No es necesario un manejo especial de 'None'.



    # --- CONTEXTO PARA LA PLANTILLA ---
    context = {
        'total_proveedores': total_proveedores,
        'total_productos': total_productos,
        'valor_inventario': valor_inventario,
        'producto_top': producto_top,
        'inventario_por_categoria': inventario_por_categoria,
        # Pasamos la variable correcta para la tabla de top productos
        'top_productos': top_productos,
        'resumen_movimientos': resumen_movimientos,
    }

    return render(request, 'index.html', context)


#======================================
#proveedores vista
#========================================

def proveedores_index(request):
    # parámetros GET
    q = request.GET.get('q', '').strip()
    order = request.GET.get('order', 'nombre_asc')
    page_size = 10

    # queryset base
    qs = Proveedor.objects.all()

    # búsqueda por nombre, rif o razón social (insensible a mayúsc/minúsc)
    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) |
            Q(rif__icontains=q) |
            Q(razonsocial__icontains=q)
        )

    # orden opcional
    if order == 'nombre_desc':
        qs = qs.order_by('-nombre')
    else:
        qs = qs.order_by('nombre')

    # paginación
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'proveedores/index.html', {
        'page_obj': page_obj,
        'q': q,
        'order': order,
    })

def proveedores_crear(request):
    formulario_proveedores = ProveedorForm(request.POST or None)
    if formulario_proveedores.is_valid():
        formulario_proveedores.save()
        return redirect('/proveedores')
    return render(request, 'proveedores/crear.html', {'formulario_proveedores': formulario_proveedores})

def proveedores_editar(request,id):
    proveedor = Proveedor.objects.get(id=id)
    formulario_proveedores = ProveedorForm(request.POST or None, instance=proveedor)
    if formulario_proveedores.is_valid() and request.POST:
        formulario_proveedores.save()
        return redirect('/proveedores')
    return render(request, 'proveedores/editar.html',{'formulario_proveedores': formulario_proveedores})

def proveedores_eliminar(request,id):
    proveedores = Proveedor.objects.get(id=id)
    proveedores.delete()
    return redirect('/proveedores')


#======================================
#inventario vista
#========================================

def inventario_index(request):
     # Query base
    qs = Inventario.objects.all()

    # Parámetros GET
    q = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    order = request.GET.get('order', 'name_asc')  # 'name_asc','name_desc','cantidad_desc','cantidad_asc'
    low = request.GET.get('low', '').strip()  # si '1' o 'true' -> filtrar los bajos
    page_size = 10

    # Filtro por texto en nombre, descripción o código
    if q:
        qs = qs.filter(
            Q(nombre_producto__icontains=q) |
            Q(descripcion__icontains=q) |
            Q(codigo_producto__icontains=q)
        )

    # Filtrar por categoría si se pasa
    if categoria:
        qs = qs.filter(categoria=categoria)

    # Filtrar sólo productos con stock bajo si se solicita
    if low and low.lower() in ('1', 'true', 'on'):
        qs = qs.filter(cantidad__lte=F('stock_minimo'))

    # Orden
    if order == 'name_desc':
        qs = qs.order_by('-nombre_producto')
    elif order == 'cantidad_desc':
        qs = qs.order_by('-cantidad')
    elif order == 'cantidad_asc':
        qs = qs.order_by('cantidad')
    else:
        qs = qs.order_by('nombre_producto')

    # Contador de productos con stock bajo (sobre el conjunto ya filtrado)
    low_stock_count = qs.filter(cantidad__lte=F('stock_minimo')).count()

    # Paginación
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'q': q,
        'categoria': categoria,
        'order': order,
        'low_stock_count': low_stock_count,
        'low': low,
    }
    return render(request, 'inventario/index.html', context)

def inventario_crear(request):
    formulario_inventario = InventarioForm(request.POST or None)
    if formulario_inventario.is_valid():
        formulario_inventario.save()
        return redirect('/inventario')
    return render(request, 'inventario/crear.html',{'formulario_inventario': formulario_inventario})

def inventario_editar(request,id_producto):
    producto = Inventario.objects.get(id_producto=id_producto)
    formulario_inventario = InventarioForm(request.POST or None, instance=producto)
    if formulario_inventario.is_valid() and request.POST:
        formulario_inventario.save()
        return redirect('/inventario')
    return render(request, 'inventario/editar.html',{'formulario_inventario': formulario_inventario})

def inventario_eliminar(request,id_producto):
    producto = Inventario.objects.get(id_producto=id_producto)
    producto.delete()
    return redirect('/inventario')


#======================================
#HistorialProveedoresNotas vista
#========================================

def historial_proveedores_notas_index(request):
    # Query base: traer notas con proveedor y por fecha (más recientes primero por defecto)
    qs = HistorialProveedoresNotas.objects.select_related('proveedores').order_by('-fecha_registro')

    # Get params
    q = request.GET.get('q', '').strip()
    days = request.GET.get('days', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    order = request.GET.get('order', 'desc')  # 'desc' o 'asc'

    # Filtro por texto en la nota o en el nombre del proveedor
    if q:
        qs = qs.filter(
            Q(detalle_nota__icontains=q) |
            Q(proveedores__nombre__icontains=q) |
            Q(proveedores__razonsocial__icontains=q)
        )

    # Filtro por últimos N días
    if days:
        try:
            n = int(days)
            cutoff = timezone.now() - timedelta(days=n)
            qs = qs.filter(fecha_registro__gte=cutoff)
        except ValueError:
            pass

    # Filtro por rango de fechas (date_from / date_to esperadas en formato YYYY-MM-DD)
    if date_from:
        try:
            qs = qs.filter(fecha_registro__date__gte=date_from)
        except Exception:
            pass
    if date_to:
        try:
            qs = qs.filter(fecha_registro__date__lte=date_to)
        except Exception:
            pass

    # Orden (permitir invertir)
    if order == 'asc':
        qs = qs.order_by('fecha_registro')
    else:
        qs = qs.order_by('-fecha_registro')

    # Paginación servidor (ajusta page_size según necesites)
    page_size = 10
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Pasar parámetros de búsqueda para mantenerlos en el formulario/links
    context = {
        'page_obj': page_obj,
        'q': q,
        'days': days,
        'date_from': date_from,
        'date_to': date_to,
        'order': order,
    }
    return render(request, 'HistorialProveedoresNotas/index.html', context)

def historial_proveedores_notas_crear(request):
    formulario_nota = HistorialProveedoresNotasForm(request.POST or None)
    if formulario_nota.is_valid():
        formulario_nota.save()
        return redirect('/HistorialProveedoresNotas')
    return render(request, 'HistorialProveedoresNotas/crear.html', {'formulario_nota': formulario_nota})

def historial_proveedores_notas_editar(request,id_historialproveedor):
    nota = HistorialProveedoresNotas.objects.get(id_historialproveedor=id_historialproveedor)
    formulario_nota = HistorialProveedoresNotasForm(request.POST or None, instance=nota)
    if formulario_nota.is_valid() and request.POST:
        formulario_nota.save()
        return redirect('/HistorialProveedoresNotas')
    return render(request, 'HistorialProveedoresNotas/editar.html',{'formulario_nota': formulario_nota})

def historial_proveedores_notas_eliminar(request,id_historialproveedor):
    nota = HistorialProveedoresNotas.objects.get(id_historialproveedor=id_historialproveedor)
    nota.delete()
    return redirect('/HistorialProveedoresNotas')

#======================================
#MovimientosInventario vista
#========================================

def movimientos_inventario_index(request):
    # Parámetros GET para filtros y orden
    q = request.GET.get('q', '').strip()
    order = request.GET.get('order', 'desc')
    page_size = 10

    # Queryset base con optimización para evitar consultas N+1
    qs = MovimientosInventario.objects.select_related('producto', 'proveedor')

    # Filtro de búsqueda por nombre de producto o proveedor
    if q:
        qs = qs.filter(
            Q(producto__nombre_producto__icontains=q) |
            Q(proveedor__nombre__icontains=q)
        )

    # Ordenamiento
    if order == 'asc':
        qs = qs.order_by('fecha_movimiento')
    else:
        qs = qs.order_by('-fecha_movimiento') # 'desc' es el default

    # Paginación
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj, 'q': q, 'order': order
    }
    return render(request, 'movimientos/index.html', context)

def movimientos_inventario_crear(request):
    formulario = MovimientosInventarioForm(request.POST or None)
    if formulario.is_valid():
        formulario.save()
        return redirect('movimientos.index')
    return render(request, 'movimientos/crear.html', {'formulario': formulario})


def movimientos_inventario_editar(request, id_movimiento):
   # 1. Obtener la instancia original del movimiento que se va a editar.
    movimiento_original = get_object_or_404(MovimientosInventario, id_movimiento=id_movimiento)
    producto = movimiento_original.producto
    
    # Guardar los valores originales antes de cualquier cambio.
    cantidad_original = movimiento_original.cantidad
    tipo_original = movimiento_original.tipo_movimiento

    if request.method == 'POST':
        # Pasar la instancia original al formulario para que sepa que es una edición.
        formulario = MovimientosInventarioForm(request.POST, instance=movimiento_original)

        if formulario.is_valid():
            # Inicia un punto de guardado dentro de la transacción.
            sid = transaction.savepoint()
            
            try:
                # 2. Revertir el efecto del movimiento original en el stock.
                if tipo_original == 'ENTRADA':
                    producto.cantidad -= cantidad_original
                elif tipo_original == 'SALIDA':
                    producto.cantidad += cantidad_original

                # Guardar temporalmente el producto con el stock revertido.
                producto.save()

                # 3. Obtener los nuevos datos del formulario sin guardarlos aún en la BD.
                movimiento_editado = formulario.save(commit=False) # El formulario ya maneja la lógica de stock
                
                # 4. Aplicar el nuevo efecto del movimiento editado.
                if movimiento_editado.tipo_movimiento == 'ENTRADA':
                    producto.cantidad += movimiento_editado.cantidad
                elif movimiento_editado.tipo_movimiento == 'SALIDA':
                    # Validar si hay stock suficiente para la nueva salida.
                    if producto.cantidad < movimiento_editado.cantidad:
                        # Si no hay stock, mostrar un error y revertir la transacción.
                        messages.error(request, f"No hay stock suficiente para registrar la salida de {movimiento_editado.cantidad} unidades. Stock disponible: {producto.cantidad}.")
                        transaction.savepoint_rollback(sid) # Revertir al estado anterior
                        
                        # Volver a renderizar el formulario con el mensaje de error.
                        return render(request, 'movimientos/editar.html', {
                            'formulario': formulario,
                        })
                    
                    producto.cantidad -= movimiento_editado.cantidad

                # 5. Guardar el producto con el stock final actualizado y el movimiento editado.
                producto.save()
                movimiento_editado.save()
                
                # Confirmar todos los cambios en la base de datos.
                transaction.savepoint_commit(sid)
                
                messages.success(request, 'El movimiento se ha actualizado y el stock ha sido ajustado correctamente.')
                return redirect('movimientos.index')

            except Exception as e:
                # En caso de un error inesperado, revertir todo.
                transaction.savepoint_rollback(sid)
                messages.error(request, f"Ocurrió un error inesperado al actualizar el movimiento: {e}")

    else:
        # Si es una petición GET, simplemente mostrar el formulario con los datos existentes.
        formulario = MovimientosInventarioForm(instance=movimiento_original)

    return render(request, 'movimientos/editar.html', {
        'formulario': formulario,
        'movimiento': movimiento_original # Para mostrar info en la plantilla si es necesario
    })


def movimientos_inventario_eliminar(request, id_movimiento):
    # Usamos select_related para traer el producto en la misma consulta
    movimiento = MovimientosInventario.objects.select_related('producto').get(id_movimiento=id_movimiento)
    
    if request.method == 'POST':
        with transaction.atomic():
            producto = movimiento.producto
            # Revertir el stock antes de eliminar el movimiento
            if movimiento.tipo_movimiento == 'ENTRADA':
                producto.cantidad -= movimiento.cantidad
            elif movimiento.tipo_movimiento == 'SALIDA':
                producto.cantidad += movimiento.cantidad
            
            producto.save()
            movimiento.delete()
        return redirect('movimientos.index')
    
    return render(request, 'movimientos/eliminar.html', {'movimiento': movimiento})


#======================================
# API para decodificar código de barras
#========================================

@csrf_exempt # Usamos csrf_exempt para simplificar el ejemplo con AJAX. En producción, considera usar el token CSRF de Django.
def decodificar_codigo_barras(request):
    if request.method == 'POST' and request.FILES.get('imagen'):
        try:
            imagen_subida = request.FILES['imagen']
            
            # Abrir la imagen usando Pillow
            img = Image.open(imagen_subida)

            # Usar pyzbar para decodificar los códigos de barras
            codigos_decodificados = decode(img)

            if not codigos_decodificados:
                return JsonResponse({'error': 'No se encontró ningún código de barras en la imagen.'}, status=400)

            # Extraer los datos del primer código encontrado
            primer_codigo = codigos_decodificados[0]
            codigo_data = primer_codigo.data.decode('utf-8')
            codigo_type = primer_codigo.type

            # Devolver el resultado como JSON
            return JsonResponse({
                'success': True,
                'codigo': codigo_data,
                'tipo': codigo_type
            })

        except Exception as e:
            return JsonResponse({'error': f'Ocurrió un error al procesar la imagen: {str(e)}'}, status=500)

    return JsonResponse({'error': 'Método no permitido o falta el archivo de imagen.'}, status=405)