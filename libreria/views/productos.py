import openpyxl
import csv
import io
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.db.models import Q, F, Sum, Min
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from datetime import timedelta, datetime
from fpdf import FPDF
from .auth import es_pleno_acceso
from ..models import Inventario, Proveedor, Lote
from ..forms import InventarioForm, ImportarArchivoForm

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_index(request):
    qs = Inventario.objects.all().annotate(
        fecha_vencimiento_min=Min(
            'lote__fecha_vencimiento',
            filter=Q(lote__cantidad_actual__gt=0),
        )
    )
    q = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    proveedor_id = request.GET.get('proveedor_id', '').strip()
    order = request.GET.get('order', 'name_asc')
    low = request.GET.get('low', '').strip()
    page_size = 10

    if q:
        qs = qs.filter(
            Q(nombre_producto__icontains=q) |
            Q(codigo_producto__icontains=q)
        )

    if categoria:
        qs = qs.filter(categoria=categoria)
        
    if proveedor_id:
        qs = qs.filter(proveedores__id=proveedor_id)

    if low and low.lower() in ('1', 'true', 'on'):
        qs = qs.filter(cantidad__lte=F('stock_minimo'))

    hace_6_dias = timezone.now() - timedelta(days=6)
    qs = qs.annotate(
        rotacion_6d=Sum(
            'movimientosinventario__cantidad',
            filter=Q(movimientosinventario__tipo_movimiento='SALIDA') & 
                   Q(movimientosinventario__fecha_movimiento__gte=hace_6_dias)
        ),
        total_entradas_hist=Sum(
            'movimientosinventario__cantidad',
            filter=Q(movimientosinventario__tipo_movimiento='ENTRADA')
        ),
        total_salidas_hist=Sum(
            'movimientosinventario__cantidad',
            filter=Q(movimientosinventario__tipo_movimiento='SALIDA')
        )
    )

    if order == 'name_desc':
        qs = qs.order_by('-nombre_producto')
    elif order == 'cantidad_desc':
        qs = qs.order_by('-cantidad')
    elif order == 'cantidad_asc':
        qs = qs.order_by('cantidad')
    elif order == 'rotacion_desc':
        qs = qs.order_by('-rotacion_6d', '-nombre_producto')
    elif order == 'rotacion_asc':
        qs = qs.order_by('rotacion_6d', 'nombre_producto')
    elif order == 'entradas_desc':
        qs = qs.order_by('-total_entradas_hist', '-nombre_producto')
    elif order == 'entradas_asc':
        qs = qs.order_by('total_entradas_hist', 'nombre_producto')
    elif order == 'salidas_desc':
        qs = qs.order_by('-total_salidas_hist', '-nombre_producto')
    elif order == 'salidas_asc':
        qs = qs.order_by('total_salidas_hist', 'nombre_producto')
    else:
        qs = qs.order_by('nombre_producto')

    low_stock_count = qs.filter(cantidad__lte=F('stock_minimo')).count()
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    proveedor_obj = None
    if proveedor_id:
        proveedor_obj = Proveedor.objects.filter(id=proveedor_id).first()

    context = {
        'page_obj': page_obj,
        'q': q,
        'categoria': categoria,
        'order': order,
        'low_stock_count': low_stock_count,
        'low': low,
        'proveedor_id': proveedor_id,
        'proveedor_obj': proveedor_obj,
        'today': timezone.now().date(),
        'threshold_date': timezone.now().date() + timedelta(days=45),
    }
    return render(request, 'inventario/index.html', context)

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_crear(request):
    formulario_inventario = InventarioForm(request.POST or None)
    if formulario_inventario.is_valid():
        formulario_inventario.save()
        messages.success(request, 'Producto registrado exitosamente.')
        return redirect('/inventario')
    return render(request, 'inventario/crear.html',{'formulario_inventario': formulario_inventario})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_editar(request, id_producto):
    producto = Inventario.objects.get(id_producto=id_producto)
    formulario_inventario = InventarioForm(request.POST or None, instance=producto)
    if formulario_inventario.is_valid() and request.POST:
        formulario_inventario.save()
        messages.success(request, 'Producto actualizado exitosamente.')
        return redirect('/inventario')
    return render(request, 'inventario/editar.html',{'formulario_inventario': formulario_inventario})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_ver(request, id_producto):
    producto = get_object_or_404(Inventario, id_producto=id_producto)
    formulario_inventario = InventarioForm(instance=producto)
    for field in formulario_inventario.fields.values():
        field.disabled = True
    return render(request, 'inventario/ver.html', {'formulario_inventario': formulario_inventario, 'solo_lectura': True})


@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_eliminar(request, id_producto):
    producto = Inventario.objects.get(id_producto=id_producto)
    producto.delete()
    messages.success(request, 'Producto eliminado exitosamente.')
    return redirect('/inventario')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
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
                        if row[0]:
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
                        cat_input = str(fila[3]).upper().strip() if len(fila) > 3 else 'OTRO'
                        categoria_valida = 'OTRO'
                        for choice in Inventario._meta.get_field('categoria').choices:
                            if choice[0] == cat_input or choice[1].upper() == cat_input:
                                categoria_valida = choice[0]
                                break
                        
                        obj, created = Inventario.objects.update_or_create(
                            codigo_producto=fila[0],
                            defaults={
                                'nombre_producto': fila[1] if len(fila) > 1 else 'Sin Nombre',
                                'descripcion': fila[2] if len(fila) > 2 else '',
                                'categoria': categoria_valida,
                                'cantidad': int(fila[4]) if len(fila) > 4 and fila[4] else 0,
                                'costo_actual': float(fila[5]) if len(fila) > 5 and fila[5] else 0.0,
                                'stock_minimo': int(fila[6]) if len(fila) > 6 and fila[6] else 5,
                                'stock_maximo': int(fila[7]) if len(fila) > 7 and fila[7] else 100,
                                'unidad_empaque': 'UNIDAD',
                                'cantidad_por_empaque': 1
                            }
                        )

                        if len(fila) > 8 and fila[8]:
                            valor_proveedor = str(fila[8]).strip()
                            proveedor = Proveedor.objects.filter(
                                Q(nombre__icontains=valor_proveedor) | Q(rif__icontains=valor_proveedor)
                            ).first()
                            if proveedor:
                                obj.proveedores.add(proveedor)
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

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def exportar_inventario_excel(request):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventario"
    headers = ["Código", "Producto", "Categoría", "Cantidad", "Unidad Empaque"]
    ws.append(headers)
    productos = Inventario.objects.all()
    for p in productos:
        ws.append([
            p.codigo_producto,
            p.nombre_producto,
            p.get_categoria_display(),
            p.cantidad,
            p.get_unidad_empaque_display()
        ])
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="inventario_reporte.xlsx"'
    wb.save(response)
    return response

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def exportar_inventario_pdf(request):
    productos = Inventario.objects.all().order_by('nombre_producto')
    total_items = productos.count()
    fecha_emision = timezone.now().strftime('%d/%m/%Y %H:%M')
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Reporte de Inventario General", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, f"Fecha de Emision: {fecha_emision}", ln=True, align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 10, f"Resumen General:", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 7, f"Total de Productos: {total_items}", ln=True)
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(30, 10, "Codigo", 1, 0, "C", True)
    pdf.cell(90, 10, "Producto", 1, 0, "C", True)
    pdf.cell(40, 10, "Categoria", 1, 0, "C", True)
    pdf.cell(30, 10, "Stock", 1, 1, "C", True)
    pdf.set_font("Helvetica", "", 8)
    for p in productos:
        nombre = p.nombre_producto[:45]
        categoria = p.get_categoria_display()[:20]
        pdf.cell(30, 8, str(p.codigo_producto), 1, 0, "L")
        pdf.cell(90, 8, nombre, 1, 0, "L")
        pdf.cell(40, 8, categoria, 1, 0, "L")
        pdf.cell(30, 8, str(p.cantidad), 1, 1, "C")
    pdf_out = pdf.output(dest='S')
    if isinstance(pdf_out, str):
        pdf_out = pdf_out.encode('latin-1')
    else:
        pdf_out = bytes(pdf_out)
    response = HttpResponse(pdf_out, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="inventario_reporte.pdf"'
    return response
@login_required
def buscar_productos_ajax(request):
    from django.http import JsonResponse
    q = request.GET.get('q', '').strip()
    if q:
        qs = Inventario.objects.filter(
            Q(nombre_producto__icontains=q) | Q(codigo_producto__icontains=q)
        )
    else:
        qs = Inventario.objects.all()
    
    # Devolvemos todos los resultados que coincidan
    productos = qs.order_by('nombre_producto')
    
    results = [
        {
            'id': p.id_producto,
            'text': f"{p.codigo_producto or 'S/C'} - {p.nombre_producto} (Stock: {p.cantidad})"
        } for p in productos
    ]
    return JsonResponse({'results': results})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_deposito_vencido(request):
    qs = Inventario.objects.filter(cantidad_vencido__gt=0)
    q = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    order = request.GET.get('order', 'name_asc')
    page_size = 10

    if q:
        qs = qs.filter(
            Q(nombre_producto__icontains=q) |
            Q(codigo_producto__icontains=q)
        )

    if categoria:
        qs = qs.filter(categoria=categoria)

    if order == 'name_desc':
        qs = qs.order_by('-nombre_producto')
    elif order == 'cantidad_desc':
        qs = qs.order_by('-cantidad_vencido')
    elif order == 'cantidad_asc':
        qs = qs.order_by('cantidad_vencido')
    else:
        qs = qs.order_by('nombre_producto')

    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Si vienen de un traslado/carga reciente, pasar el lote para el modal de PDF
    pdf_lote = request.session.pop('ultimo_vencido_pdf_lote', None)
    pdf_tipo = request.session.pop('ultimo_vencido_pdf_tipo', None)

    context = {
        'page_obj': page_obj,
        'q': q,
        'categoria': categoria,
        'order': order,
        'titulo': 'Depósito de Productos Vencidos',
        'pdf_lote': pdf_lote,
        'pdf_tipo': pdf_tipo,
    }
    return render(request, 'inventario/deposito_vencido.html', context)

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_ajuste_existencia(request):
    return render(request, 'inventario/ajuste_existencia/index.html')


def _parse_ajuste_lote_inicial(request):
    producto_ids = request.POST.getlist('producto_id[]')
    lote_ids = request.POST.getlist('lote_inicial_id[]')
    cantidades = request.POST.getlist('cantidad[]')
    lote_nuevos = request.POST.getlist('lote_nuevo[]')
    fechas = request.POST.getlist('fecha_vencimiento[]')

    items = []
    errores = []

    for idx in range(len(producto_ids)):
        try:
            cantidad = int(cantidades[idx])
        except (ValueError, IndexError):
            continue
        if cantidad <= 0:
            continue

        lote_id = lote_ids[idx] if idx < len(lote_ids) else ''
        lote = Lote.objects.select_related('producto').filter(id_lote=lote_id).first()
        if not lote:
            errores.append('Uno de los lotes iniciales seleccionados ya no existe.')
            continue
        if not (lote.codigo_lote or '').startswith('LOTE-INICIAL-'):
            errores.append(f'El lote {lote.codigo_lote} no es un lote inicial.')
            continue
        if cantidad > lote.cantidad_actual:
            errores.append(
                f'La cantidad para {lote.producto.nombre_producto} supera el stock '
                f'disponible del lote inicial ({lote.cantidad_actual}).'
            )
            continue

        fecha_str = fechas[idx] if idx < len(fechas) else ''
        try:
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            errores.append(f'Fecha de vencimiento inválida para {lote.producto.nombre_producto}.')
            continue

        codigo_nuevo = (lote_nuevos[idx] if idx < len(lote_nuevos) else '').strip()
        if not codigo_nuevo:
            codigo_nuevo = f"AJ-{lote.producto_id}-{int(timezone.now().timestamp())}"

        items.append({
            'producto': lote.producto,
            'lote_inicial': lote,
            'cantidad': cantidad,
            'stock_inicial_restante': lote.cantidad_actual - cantidad,
            'lote_nuevo': codigo_nuevo,
            'fecha_vencimiento': fecha,
        })

    return items, errores


@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_ajuste_lote_inicial(request):
    lotes_iniciales = (
        Lote.objects.filter(
            codigo_lote__startswith='LOTE-INICIAL-',
            cantidad_actual__gt=0,
        )
        .select_related('producto')
        .order_by('producto__nombre_producto', 'fecha_vencimiento')
    )

    productos = {}
    for lote in lotes_iniciales:
        p = lote.producto
        data = productos.setdefault(p.id_producto, {
            'id': p.id_producto,
            'nombre': p.nombre_producto or '',
            'codigo': p.codigo_producto or '',
            'stock': p.cantidad,
            'lotes': [],
        })
        data['lotes'].append({
            'id': lote.id_lote,
            'codigo': lote.codigo_lote,
            'cantidad': lote.cantidad_actual,
            'fecha_vencimiento': lote.fecha_vencimiento.strftime('%Y-%m-%d') if lote.fecha_vencimiento else '',
        })

    return render(request, 'inventario/ajuste_existencia/lote_inicial.html', {
        'productos_json': list(productos.values()),
    })


@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_ajuste_lote_inicial_confirmar(request):
    if request.method != 'POST':
        return redirect('inventario.ajuste_lote_inicial')

    items, errores = _parse_ajuste_lote_inicial(request)
    if errores:
        for error in errores:
            messages.error(request, error)
        return redirect('inventario.ajuste_lote_inicial')
    if not items:
        messages.warning(request, 'Debe seleccionar al menos un producto con una cantidad mayor a cero.')
        return redirect('inventario.ajuste_lote_inicial')

    return render(
        request,
        'inventario/ajuste_existencia/confirmar_lote_inicial.html',
        {'items': items},
    )


@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_ajuste_lote_inicial_procesar(request):
    if request.method != 'POST':
        return redirect('inventario.ajuste_lote_inicial')

    items, errores = _parse_ajuste_lote_inicial(request)
    if errores or not items:
        for error in errores:
            messages.error(request, error)
        if not items and not errores:
            messages.warning(request, 'Debe seleccionar al menos un producto con una cantidad mayor a cero.')
        return redirect('inventario.ajuste_lote_inicial')

    try:
        with transaction.atomic():
            for item in items:
                lote = Lote.objects.select_for_update().get(id_lote=item['lote_inicial'].id_lote)
                if item['cantidad'] > lote.cantidad_actual:
                    raise ValueError(
                        f'El stock del lote inicial de {lote.producto.nombre_producto} cambió. '
                        'Vuelva a intentarlo.'
                    )
                lote.cantidad_actual -= item['cantidad']
                lote.save(update_fields=['cantidad_actual'])
                Lote.objects.create(
                    producto=lote.producto,
                    codigo_lote=item['lote_nuevo'],
                    fecha_vencimiento=item['fecha_vencimiento'],
                    fecha_llegada=timezone.now().date(),
                    cantidad_actual=item['cantidad'],
                )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('inventario.ajuste_lote_inicial')

    messages.success(
        request,
        f'Se reorganizaron {len(items)} lote(s) inicial(es). El stock total no cambió.',
    )
    return redirect('lotes.index')


@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def inventario_ajuste_cantidad_exacta(request):
    if request.method == 'POST':
        producto = Inventario.objects.filter(pk=request.POST.get('producto_id')).first()
        if not producto:
            messages.error(request, 'Seleccione un producto válido.')
            return redirect('inventario.ajuste_cantidad_exacta')

        try:
            nueva_cantidad = int(request.POST.get('cantidad', ''))
        except (TypeError, ValueError):
            messages.error(request, 'Ingrese una cantidad entera válida.')
            return redirect('inventario.ajuste_cantidad_exacta')

        if nueva_cantidad < 0:
            messages.error(request, 'La cantidad no puede ser negativa.')
            return redirect('inventario.ajuste_cantidad_exacta')

        with transaction.atomic():
            producto = Inventario.objects.select_for_update().get(pk=producto.pk)
            lotes = list(
                Lote.objects.select_for_update()
                .filter(producto=producto)
                .order_by('fecha_vencimiento', 'id_lote')
            )
            total_lotes = sum(lote.cantidad_actual for lote in lotes)

            if nueva_cantidad > total_lotes:
                diferencia = nueva_cantidad - total_lotes
                lote_destino = next(
                    (lote for lote in lotes if (lote.codigo_lote or '').startswith('LOTE-INICIAL-')),
                    None,
                )
                if lote_destino is None and lotes:
                    lote_destino = lotes[-1]
                if lote_destino is None:
                    Lote.objects.create(
                        producto=producto,
                        codigo_lote=f"AJUSTE-{producto.codigo_producto}-{timezone.now():%Y%m%d%H%M%S}",
                        fecha_vencimiento=timezone.now().date() + timedelta(days=365),
                        fecha_llegada=timezone.now().date(),
                        cantidad_actual=diferencia,
                    )
                else:
                    lote_destino.cantidad_actual += diferencia
                    lote_destino.save(update_fields=['cantidad_actual'])
            elif nueva_cantidad < total_lotes:
                restante = total_lotes - nueva_cantidad
                for lote in lotes:
                    if restante <= 0:
                        break
                    tomar = min(lote.cantidad_actual, restante)
                    if tomar:
                        lote.cantidad_actual -= tomar
                        lote.save(update_fields=['cantidad_actual'])
                        restante -= tomar

            producto.cantidad = nueva_cantidad
            producto.save(update_fields=['cantidad'])

        messages.success(
            request,
            f'Cantidad de «{producto.nombre_producto}» actualizada a {nueva_cantidad}.',
        )
        return redirect('inventario.ajuste_cantidad_exacta')

    return render(request, 'inventario/ajuste_existencia/cantidad_exacta.html')


@login_required
def api_buscar_producto_stock(request):
    q = request.GET.get('q', '').strip()
    if not q or len(q) < 2:
        return JsonResponse({'success': True, 'productos': []})
    
    productos = Inventario.objects.filter(
        Q(nombre_producto__icontains=q) |
        Q(codigo_producto__icontains=q)
    )[:10]
    
    data = []
    for p in productos:
        data.append({
            'id': p.id_producto,
            'codigo': p.codigo_producto,
            'nombre': p.nombre_producto,
            'stock': p.cantidad,
            'vencido': p.cantidad_vencido,
            'total_empaques': p.total_empaques,
            'unidad': p.get_unidad_empaque_display()
        })
        
    return JsonResponse({'success': True, 'productos': data})
