from django.shortcuts import render, redirect
from django.http import HttpResponse
from .models import Cliente, Proveedor, Inventario, HistorialProveedoresNotas, MovimientosInventario, PerfilUsuario
from .forms import ClienteForm, ProveedorForm, InventarioForm, HistorialProveedoresNotasForm, MovimientosInventarioForm, UserForm, PerfilUsuarioForm, ImportarArchivoForm
from django.core.paginator import Paginator
from django.db.models import Q, F, Sum, Count, Value
from django.utils import timezone
from django.db import transaction
from datetime import timedelta, datetime
from django.shortcuts import get_object_or_404
from django import forms
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from PIL import Image, ImageEnhance
from pyzbar.pyzbar import decode
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth import logout
from django.core.management import call_command
import openpyxl
import csv
import io
from django.template.loader import get_template
from xhtml2pdf import pisa
# Create your views here.
# libreria/views.py
 
import json

# En tu archivo views.py (ejemplo de la lógica actual)
from django.db.models import Count
# ...
def custom_logout(request):
    logout(request)
    return redirect('login')

# --- Decorador para verificar rol de Administrador ---
def es_admin(user):
    return hasattr(user, 'perfilusuario') and user.perfilusuario.rol == 'admin'

def es_inventario_acceso(user):
    return hasattr(user, 'perfilusuario') and user.perfilusuario.rol in ['admin', 'inventario']

@login_required
def index(request):
    # --- CÁLCULO PARA LAS TARJETAS (CARDS) ---

    # 1. Total de proveedores
    total_proveedores = Proveedor.objects.count()

    # 2. Total de productos
    total_productos = Inventario.objects.count()

    # 3. Valor total del inventario (usando 'cantidad' y 'costo_actual' de tu modelo)
    valor_inventario = Inventario.objects.aggregate(
        total=Sum(F('cantidad') * F('costo_actual'))
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

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
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

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def proveedores_crear(request):
    formulario_proveedores = ProveedorForm(request.POST or None)
    if formulario_proveedores.is_valid():
        formulario_proveedores.save()
        return redirect('/proveedores')
    return render(request, 'proveedores/crear.html', {'formulario_proveedores': formulario_proveedores})

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def proveedores_editar(request,id):
    proveedor = Proveedor.objects.get(id=id)
    formulario_proveedores = ProveedorForm(request.POST or None, instance=proveedor)
    if formulario_proveedores.is_valid() and request.POST:
        formulario_proveedores.save()
        return redirect('/proveedores')
    return render(request, 'proveedores/editar.html',{'formulario_proveedores': formulario_proveedores})

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def proveedores_eliminar(request,id):
    proveedores = Proveedor.objects.get(id=id)
    proveedores.delete()
    return redirect('/proveedores')

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def proveedores_importar(request):
    if request.method == 'POST':
        form = ImportarArchivoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            nombre_archivo = archivo.name.lower()
            registros_creados = 0
            errores = []

            try:
                # Determinar si es Excel o CSV
                datos = []
                if nombre_archivo.endswith('.xlsx'):
                    wb = openpyxl.load_workbook(archivo)
                    ws = wb.active
                    # Iterar filas, saltando la cabecera (min_row=2)
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        # Esperamos: Nombre, Telefono, Razon Social, RIF, Direccion
                        if row[0]: # Si hay nombre
                            datos.append(row)
                elif nombre_archivo.endswith('.csv') or nombre_archivo.endswith('.txt'):
                    archivo_data = archivo.read().decode('utf-8')
                    io_string = io.StringIO(archivo_data)
                    reader = csv.reader(io_string, delimiter=',')
                    next(reader, None) # Saltar cabecera
                    for row in reader:
                        if row and row[0]:
                            datos.append(row)
                
                # Procesar datos
                for i, fila in enumerate(datos):
                    try:
                        # Asumiendo orden: Nombre, Telefono, Razon Social, RIF, Direccion
                        Proveedor.objects.create(
                            nombre=fila[0],
                            telefono=fila[1] if len(fila) > 1 else '',
                            razonsocial=fila[2] if len(fila) > 2 else '',
                            rif=fila[3] if len(fila) > 3 else f"S/R-{i}", # RIF es unique, cuidado
                            direccion=fila[4] if len(fila) > 4 else ''
                        )
                        registros_creados += 1
                    except Exception as e:
                        errores.append(f"Fila {i+2}: {str(e)}")

                messages.success(request, f'Se importaron {registros_creados} proveedores correctamente.')
                if errores:
                    messages.warning(request, f'Hubo errores en {len(errores)} filas. Primera falla: {errores[0]}')
                return redirect('proveedores.index')

            except Exception as e:
                messages.error(request, f'Error procesando el archivo: {str(e)}')

    else:
        form = ImportarArchivoForm()

    return render(request, 'proveedores/importar.html', {'form': form})

#======================================
#inventario vista
#========================================

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
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

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def inventario_crear(request):
    formulario_inventario = InventarioForm(request.POST or None)
    if formulario_inventario.is_valid():
        formulario_inventario.save()
        return redirect('/inventario')
    return render(request, 'inventario/crear.html',{'formulario_inventario': formulario_inventario})

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def inventario_editar(request,id_producto):
    producto = Inventario.objects.get(id_producto=id_producto)
    formulario_inventario = InventarioForm(request.POST or None, instance=producto)
    if formulario_inventario.is_valid() and request.POST:
        formulario_inventario.save()
        return redirect('/inventario')
    return render(request, 'inventario/editar.html',{'formulario_inventario': formulario_inventario})

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def inventario_eliminar(request,id_producto):
    producto = Inventario.objects.get(id_producto=id_producto)
    producto.delete()
    return redirect('/inventario')

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def inventario_importar(request):
    if request.method == 'POST':
        form = ImportarArchivoForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            nombre_archivo = archivo.name.lower()
            registros_creados = 0
            errores = []

            try:
                datos = []
                if nombre_archivo.endswith('.xlsx'):
                    wb = openpyxl.load_workbook(archivo)
                    ws = wb.active
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        if row[0]: # Si hay código o nombre
                            datos.append(row)
                elif nombre_archivo.endswith('.csv') or nombre_archivo.endswith('.txt'):
                    archivo_data = archivo.read().decode('utf-8')
                    io_string = io.StringIO(archivo_data)
                    reader = csv.reader(io_string, delimiter=',')
                    next(reader, None)
                    for row in reader:
                        if row:
                            datos.append(row)

                for i, fila in enumerate(datos):
                    try:
                        # Orden esperado: Codigo, Nombre, Descripcion, Categoria, Cantidad, Costo, StockMin, StockMax
                        # Mapeo simple de categoría (si no coincide, usa OTRO)
                        cat_input = str(fila[3]).upper().strip() if len(fila) > 3 else 'OTRO'
                        categoria_valida = 'OTRO'
                        for choice in Inventario._meta.get_field('categoria').choices:
                            if choice[0] == cat_input or choice[1].upper() == cat_input:
                                categoria_valida = choice[0]
                                break
                        
                        Inventario.objects.create(
                            codigo_producto=fila[0],
                            nombre_producto=fila[1] if len(fila) > 1 else 'Sin Nombre',
                            descripcion=fila[2] if len(fila) > 2 else '',
                            categoria=categoria_valida,
                            cantidad=int(fila[4]) if len(fila) > 4 and fila[4] else 0,
                            costo_actual=float(fila[5]) if len(fila) > 5 and fila[5] else 0.0,
                            stock_minimo=int(fila[6]) if len(fila) > 6 and fila[6] else 5,
                            stock_maximo=int(fila[7]) if len(fila) > 7 and fila[7] else 100,
                            # Valores por defecto para campos no obligatorios en excel simple
                            unidad_empaque='UNIDAD',
                            cantidad_por_empaque=1
                        )
                        registros_creados += 1
                    except Exception as e:
                        errores.append(f"Fila {i+2} ({fila[0] if fila else '?'}): {str(e)}")

                messages.success(request, f'Se importaron {registros_creados} productos.')
                if errores:
                    messages.warning(request, f'Errores: {len(errores)}. {errores[0]}')
                return redirect('inventario.index')
            except Exception as e:
                messages.error(request, f'Error general: {str(e)}')
    else:
        form = ImportarArchivoForm()
    return render(request, 'inventario/importar.html', {'form': form})

# --- EXPORTACIÓN DE INFORMES ---

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def exportar_inventario_excel(request):
    # Crear un libro de trabajo (workbook)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventario"

    # Encabezados
    headers = ["Código", "Producto", "Categoría", "Cantidad", "Unidad Empaque", "Costo Actual", "Valor Total"]
    ws.append(headers)

    # Obtener datos (puedes aplicar los mismos filtros que en el index si quisieras, aquí exportamos todo)
    productos = Inventario.objects.all()

    for p in productos:
        valor_total = p.cantidad * p.costo_actual
        ws.append([
            p.codigo_producto,
            p.nombre_producto,
            p.get_categoria_display(),
            p.cantidad,
            p.get_unidad_empaque_display(),
            p.costo_actual,
            valor_total
        ])

    # Preparar la respuesta HTTP
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="inventario_reporte.xlsx"'
    
    wb.save(response)
    return response

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def exportar_inventario_pdf(request):
    # Obtener datos
    productos = Inventario.objects.all().order_by('nombre_producto')
    
    # Calcular totales generales para el reporte
    total_items = productos.count()
    valor_total_inventario = sum(p.cantidad * p.costo_actual for p in productos)

    context = {
        'productos': productos,
        'total_items': total_items,
        'valor_total_inventario': valor_total_inventario,
        'fecha_emision': timezone.now()
    }

    # Renderizar template
    template_path = 'inventario/reporte_pdf.html'
    template = get_template(template_path)
    html = template.render(context)

    # Crear respuesta PDF
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventario_reporte.pdf"'

    # Generar PDF
    pisa_status = pisa.CreatePDF(html, dest=response)
    
    if pisa_status.err:
        return HttpResponse('Hubo un error al generar el PDF <pre>' + html + '</pre>')
    return response

#======================================
#HistorialProveedoresNotas vista
#========================================

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
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

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def historial_proveedores_notas_crear(request):
    formulario_nota = HistorialProveedoresNotasForm(request.POST or None)
    if formulario_nota.is_valid():
        formulario_nota.save()
        return redirect('/HistorialProveedoresNotas')
    return render(request, 'HistorialProveedoresNotas/crear.html', {'formulario_nota': formulario_nota})

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def historial_proveedores_notas_editar(request,id_historialproveedor):
    nota = HistorialProveedoresNotas.objects.get(id_historialproveedor=id_historialproveedor)
    formulario_nota = HistorialProveedoresNotasForm(request.POST or None, instance=nota)
    if formulario_nota.is_valid() and request.POST:
        formulario_nota.save()
        return redirect('/HistorialProveedoresNotas')
    return render(request, 'HistorialProveedoresNotas/editar.html',{'formulario_nota': formulario_nota})

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def historial_proveedores_notas_eliminar(request,id_historialproveedor):
    nota = HistorialProveedoresNotas.objects.get(id_historialproveedor=id_historialproveedor)
    nota.delete()
    return redirect('/HistorialProveedoresNotas')

#======================================
#MovimientosInventario vista
#========================================

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
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
            Q(proveedor__nombre__icontains=q) |
            Q(proveedor__razonsocial__icontains=q) |
            Q(proveedor__rif__icontains=q)
        )

    # Calcular totales solo si hay un filtro de búsqueda activo
    resumen_filtro = None
    if q:
        resumen_filtro = qs.aggregate(
            total_entradas=Sum('cantidad', filter=Q(tipo_movimiento='ENTRADA')),
            total_salidas=Sum('cantidad', filter=Q(tipo_movimiento='SALIDA'))
        )
        
        # Calcular el stock actual de los productos encontrados en la búsqueda
        ids_productos = qs.values_list('producto_id', flat=True).distinct()
        stock_actual = Inventario.objects.filter(id_producto__in=ids_productos).aggregate(total=Sum('cantidad'))['total']
        resumen_filtro['stock_actual'] = stock_actual if stock_actual is not None else 0

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
        'page_obj': page_obj, 'q': q, 'order': order,
        'resumen_filtro': resumen_filtro
    }
    return render(request, 'movimientos/index.html', context)

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_inventario_crear(request):
    formulario = MovimientosInventarioForm(request.POST or None)
    
    # Crear diccionario de datos de productos para JS para el cálculo en el frontend
    # Obtenemos el mapa de opciones para mostrar la etiqueta legible (ej. "Caja (6, 12...)") en lugar del código ("CAJA")
    choices_map = dict(Inventario._meta.get_field('unidad_empaque').choices)
    
    productos_info = Inventario.objects.values('id_producto', 'cantidad_por_empaque', 'unidad_empaque')
    # Mapeamos 'unidad' usando choices_map.get()
    productos_data = {str(p['id_producto']): {
        'factor': p['cantidad_por_empaque'], 
        'unidad': choices_map.get(p['unidad_empaque'], p['unidad_empaque']),
        'unidad_codigo': p['unidad_empaque']
    } for p in productos_info}
    
    if formulario.is_valid():
        formulario.save()
        messages.success(request, 'Movimiento registrado y stock actualizado correctamente.')
        return redirect('movimientos.index')

    return render(request, 'movimientos/crear.html', {
        'formulario': formulario, 
        'productos_data': json.dumps(productos_data)
    })


@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_inventario_editar(request, id_movimiento):
    movimiento = get_object_or_404(MovimientosInventario, id_movimiento=id_movimiento)
    
    # Datos para JS
    choices_map = dict(Inventario._meta.get_field('unidad_empaque').choices)
    productos_info = Inventario.objects.values('id_producto', 'cantidad_por_empaque', 'unidad_empaque')
    productos_data = {str(p['id_producto']): {
        'factor': p['cantidad_por_empaque'], 
        'unidad': choices_map.get(p['unidad_empaque'], p['unidad_empaque']),
        'unidad_codigo': p['unidad_empaque']
    } for p in productos_info}

    if request.method == 'POST':
        formulario = MovimientosInventarioForm(request.POST, instance=movimiento)
        if formulario.is_valid():
            # El método save del formulario maneja toda la lógica de stock y transacciones.
            # Puede lanzar ValidationError si el stock es insuficiente durante la edición.
            try:
                formulario.save()
                messages.success(request, 'El movimiento se ha actualizado y el stock ha sido ajustado correctamente.')
                return redirect('movimientos.index')
            except forms.ValidationError as e:
                # Agrega el error al formulario para que se muestre en la plantilla
                formulario.add_error(None, e)
    else:
        formulario = MovimientosInventarioForm(instance=movimiento)

    return render(request, 'movimientos/editar.html', {
        'formulario': formulario,
        'movimiento': movimiento,
        'productos_data': json.dumps(productos_data)
    })


@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
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

@login_required
@csrf_exempt # Usamos csrf_exempt para simplificar el ejemplo con AJAX. En producción, considera usar el token CSRF de Django.
def decodificar_codigo_barras(request):
    if request.method == 'POST' and request.FILES.get('imagen'):
        try:
            imagen_subida = request.FILES['imagen']
            
            # --- INICIO DE MEJORAS DE IMAGEN ---
            img = Image.open(imagen_subida)

            # 1. Convertir a escala de grises (mejora la detección)
            img = img.convert('L')

            # 2. Aumentar el contraste para que las barras sean más nítidas
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(2.0) # El valor 2.0 es un buen punto de partida, puedes ajustarlo

            # 3. (NUEVO) Binarización: Convertir la imagen a blanco y negro puros.
            #    Esto es muy efectivo para que el lector se enfoque solo en las barras.
            #    Un umbral de 128 es un buen valor inicial.
            umbral = 128
            img = img.point(lambda p: 255 if p > umbral else 0)
            img = img.convert('1') # Convertir al modo de 1-bit (blanco y negro)


            # --- PASO DE DEPURACIÓN: GUARDAR LA IMAGEN PROCESADA ---
            # Descomenta la siguiente línea para guardar la imagen final.
            # Se guardará en la carpeta principal de tu proyecto.
            # Revisa este archivo para ver si el código de barras es legible.
            img.save("imagen_procesada_final.png")

            # --- FIN DE MEJORAS DE IMAGEN ---

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

#usuarios views
@login_required
# Solo admin puede ver la lista
@user_passes_test(es_admin, login_url='index')
def usuarios_index(request):
    # Parámetros GET
    q = request.GET.get('q', '').strip()
    page_size = 10

    # Usamos el modelo Cliente que ya está importado
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
 # Solo admin puede crear
@user_passes_test(es_admin, login_url='index')
def usuarios_crear(request):
    if request.method == 'POST':
        user_form = UserForm(request.POST)
        perfil_form = PerfilUsuarioForm(request.POST)
        if user_form.is_valid() and perfil_form.is_valid():
            user = user_form.save()
            
            # Al guardar el usuario, la señal ya creó el perfil. Lo recuperamos y actualizamos.
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
def usuarios_editar(request,id):
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
@user_passes_test(es_admin, login_url='index') # Solo admin puede eliminar
@user_passes_test(es_admin, login_url='index')
def usuarios_eliminar(request,id):
    perfil = get_object_or_404(PerfilUsuario, id=id)
    perfil.user.delete() # Esto elimina el usuario y el perfil en cascada
    messages.success(request, 'Usuario eliminado exitosamente.')
    return redirect('usuarios.index') 

# ======================================
# BACKUPS / COPIAS DE SEGURIDAD
# ======================================

@login_required
@user_passes_test(es_admin, login_url='index')
def realizar_copia_seguridad(request):
    # Buffer para capturar los datos en memoria
    output = io.StringIO()
    
    # Ejecutamos 'dumpdata' para exportar 'auth.User' (usuarios) y toda la app 'libreria'
    # Esto crea un archivo JSON compatible con cualquier base de datos Django
    call_command('dumpdata', 'auth.User', 'libreria', stdout=output)

    # Preparamos la respuesta para descargar el archivo
    response = HttpResponse(output.getvalue(), content_type='application/json')
    filename = f"backup_inventario_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.json"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response