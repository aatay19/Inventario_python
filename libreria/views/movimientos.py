import uuid
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum, Max, Count
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django import forms
from .auth import es_inventario_acceso, es_pleno_acceso, es_almacenista_o_superior
from ..models import MovimientosInventario, Inventario, Proveedor, HistorialProveedoresNotas, PedidoCompra
from ..forms import MovimientosInventarioForm, HistorialProveedoresNotasForm

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_inventario_index(request):
    q = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    order = request.GET.get('order', 'desc')
    page_size = 10
    qs = MovimientosInventario.objects.select_related('producto', 'proveedor')

    if q:
        qs = qs.filter(
            Q(producto__nombre_producto__icontains=q) |
            Q(proveedor__razonsocial__icontains=q) |
            Q(proveedor__rif__icontains=q)
        )

    if date_from:
        try:
            fecha_inicio = datetime.strptime(date_from, '%Y-%m-%d')
            qs = qs.filter(fecha_movimiento__gte=fecha_inicio)
        except ValueError:
            pass
    if date_to:
        try:
            fecha_fin = datetime.strptime(date_to, '%Y-%m-%d')
            fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
            qs = qs.filter(fecha_movimiento__lte=fecha_fin)
        except ValueError:
            pass

    resumen_filtro = None
    if q:
        resumen_por_producto = qs.values('producto__nombre_producto', 'producto__unidad_empaque') \
                                 .annotate(
                                     entradas=Sum('cantidad_empaques', default=0.0, filter=Q(tipo_movimiento='ENTRADA')),
                                     salidas=Sum('cantidad_empaques', default=0.0, filter=Q(tipo_movimiento='SALIDA'))
                                 ).order_by('producto__nombre_producto')
        
        entradas_str_parts = []
        salidas_str_parts = []
        total_entradas_general = 0.0
        total_salidas_general = 0.0

        for item in resumen_por_producto:
            unidad = item.get('producto__unidad_empaque') or 'Empaque'
            if item['entradas'] and item['entradas'] > 0:
                val = f"{item['entradas']:.2f}".rstrip('0').rstrip('.')
                entradas_str_parts.append(f"{val} {unidad} ({item['producto__nombre_producto']})")
                total_entradas_general += item['entradas']
            if item['salidas'] and item['salidas'] > 0:
                val = f"{item['salidas']:.2f}".rstrip('0').rstrip('.')
                salidas_str_parts.append(f"{val} {unidad} ({item['producto__nombre_producto']})")
                total_salidas_general += item['salidas']

        ids_productos = qs.values_list('producto_id', flat=True).distinct()
        productos_stock = Inventario.objects.filter(id_producto__in=ids_productos).values('nombre_producto', 'cantidad', 'cantidad_por_empaque', 'unidad_empaque').order_by('nombre_producto')
        
        stock_desglose = []
        total_stock_general = 0.0
        for p in productos_stock:
            factor = p.get('cantidad_por_empaque') or 1
            cant = p['cantidad'] / factor
            val = f"{cant:.2f}".rstrip('0').rstrip('.')
            unidad = p.get('unidad_empaque') or 'Empaque'
            stock_desglose.append(f"{val} {unidad} ({p['nombre_producto']})")
            total_stock_general += cant

        total_entradas_str = f"{total_entradas_general:.2f}".rstrip('0').rstrip('.') or '0'
        total_salidas_str = f"{total_salidas_general:.2f}".rstrip('0').rstrip('.') or '0'
        total_stock_str = f"{total_stock_general:.2f}".rstrip('0').rstrip('.') or '0'

        resumen_filtro = {
            'entradas_desglose': entradas_str_parts,
            'salidas_desglose': salidas_str_parts,
            'stock_desglose': stock_desglose,
            'total_entradas_general': total_entradas_str,
            'total_salidas_general': total_salidas_str,
            'stock_actual': total_stock_str
        }

    if q:
        if order == 'asc':
            qs = qs.order_by('producto__nombre_producto', 'fecha_movimiento')
        else:
            qs = qs.order_by('producto__nombre_producto', '-fecha_movimiento')
    else:
        if order == 'asc':
            qs = qs.order_by('fecha_movimiento')
        else:
            qs = qs.order_by('-fecha_movimiento')

    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj, 'q': q, 'order': order,
        'resumen_filtro': resumen_filtro,
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'movimientos/index.html', context)

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_inventario_crear(request):
    formulario = MovimientosInventarioForm(request.POST or None)
    if formulario.is_valid():
        formulario.save()
        messages.success(request, 'Movimiento registrado y stock actualizado correctamente.')
        return redirect('movimientos.index')
    return render(request, 'movimientos/crear.html', {'formulario': formulario})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_inventario_editar(request, id_movimiento):
    movimiento = get_object_or_404(MovimientosInventario, id_movimiento=id_movimiento)
    if request.method == 'POST':
        formulario = MovimientosInventarioForm(request.POST, instance=movimiento)
        if formulario.is_valid():
            try:
                # Si no tiene lote, le asignamos uno al editar para que aparezca agrupado en el historial
                if not movimiento.codigo_lote:
                    import uuid
                    ahora = timezone.now()
                    movimiento.codigo_lote = f"ED-{ahora.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8]}"
                
                formulario.save()
                messages.success(request, 'El movimiento se ha actualizado y el stock ha sido ajustado correctamente.')
                return redirect('movimientos.index')
            except forms.ValidationError as e:
                formulario.add_error(None, e)
    else:
        formulario = MovimientosInventarioForm(instance=movimiento)
    return render(request, 'movimientos/editar.html', {'formulario': formulario, 'movimiento': movimiento})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_inventario_eliminar(request, id_movimiento):
    movimiento = MovimientosInventario.objects.select_related('producto').get(id_movimiento=id_movimiento)
    if request.method == 'POST':
        with transaction.atomic():
            producto = movimiento.producto
            if movimiento.tipo_movimiento == 'ENTRADA':
                producto.cantidad -= movimiento.cantidad
            elif movimiento.tipo_movimiento == 'SALIDA':
                producto.cantidad += movimiento.cantidad
            producto.save()
            movimiento.delete()
        messages.success(request, 'Movimiento eliminado exitosamente.')
        return redirect('movimientos.index')
    return render(request, 'movimientos/eliminar.html', {'movimiento': movimiento})

@login_required
@user_passes_test(es_almacenista_o_superior, login_url='index')
def movimientos_salida_form(request):
    from ..models import UnidadEmpaqueChoices
    qs = Inventario.objects.all().order_by('nombre_producto')
    unidades_choices = UnidadEmpaqueChoices.choices
    unidades_html = "".join([f'<option value="{v}">{l}</option>' for v, l in unidades_choices])
    hace_6_dias = timezone.now() - timedelta(days=6)
    rotacion_map = {
        item['producto_id']: item['total']
        for item in MovimientosInventario.objects.filter(
            tipo_movimiento='SALIDA',
            fecha_movimiento__gte=hace_6_dias
        ).values('producto_id').annotate(total=Sum('cantidad'))
    }
    productos_json = []
    for p in qs:
        productos_json.append({
            'id': p.id_producto,
            'nombre': str(p.nombre_producto or ""),
            'codigo': str(p.codigo_producto or ""),
            'stock': p.cantidad,
            'rotacion': rotacion_map.get(p.id_producto, 0),
            'unidades_html': unidades_html,
            'id_unidad_default': p.unidad_empaque,
            'cant_por_empaque': p.cantidad_por_empaque,
            'total_empaques': p.total_empaques
        })
    return render(request, 'movimientos/form_salida.html', {
        'productos_json': productos_json,
        'unidades_choices': unidades_choices,
    })

@login_required
@user_passes_test(es_almacenista_o_superior, login_url='index')
def movimientos_salida_confirmar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        cants_por_empaque = request.POST.getlist('cant_por_empaque[]')
        items_resumen = []
        for i in range(len(producto_ids)):
            cant = int(totales[i])
            if cant > 0:
                producto = Inventario.objects.get(id_producto=producto_ids[i])
                items_resumen.append({
                    'producto': producto,
                    'unidad': unidades_empaque[i],
                    'cant_por_empaque': cants_por_empaque[i] if cants_por_empaque and i < len(cants_por_empaque) else producto.cantidad_por_empaque,
                    'cant_empaques': cants_empaques[i],
                    'total': cant,
                })
        if not items_resumen:
            messages.warning(request, "Debe seleccionar al menos un producto con cantidad mayor a cero.")
            return redirect('movimientos.salida')
        proveedores = Proveedor.objects.all().order_by('razonsocial')
        return render(request, 'movimientos/confirmar_salida.html', {
            'items': items_resumen,
            'proveedores': proveedores
        })
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_almacenista_o_superior, login_url='index')
def movimientos_salida_procesar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        proveedor_id = request.POST.get('proveedor_id')
        proveedor = None
        if proveedor_id:
            proveedor = Proveedor.objects.get(id=proveedor_id)
        ahora = timezone.now()
        lote_id = f"S-{ahora.strftime('%Y%m%d%H%M')}-{str(uuid.uuid4())[:8]}"
        salidas_creadas = 0
        try:
            with transaction.atomic():
                for i in range(len(producto_ids)):
                    producto = Inventario.objects.get(id_producto=producto_ids[i])
                    cant_salida = int(totales[i])
                    if cant_salida > 0:
                        if producto.cantidad < cant_salida:
                            raise forms.ValidationError(f"Stock insuficiente para {producto.nombre_producto}. Disponible: {producto.cantidad}")
                        MovimientosInventario.objects.create(
                            producto=producto,
                            tipo_movimiento='SALIDA',
                            cantidad=cant_salida,
                            unidad_empaque=unidades_empaque[i],
                            cantidad_empaques=float(cants_empaques[i]) if cants_empaques[i] else 0.0,
                            proveedor=proveedor,
                            fecha_movimiento=ahora,
                            codigo_lote=lote_id
                        )
                        producto.cantidad -= cant_salida
                        producto.save()
                        salidas_creadas += 1
            
            if proveedor:
                razon_social = proveedor.razonsocial
                msg = f'Se registraron exitosamente {salidas_creadas} salidas del inventario con descargo a {razon_social}.'
            else:
                razon_social = "Sin especificar"
                msg = f'Se registraron exitosamente {salidas_creadas} salidas del inventario.'
                
            messages.success(request, msg)
            request.session['ultimo_pdf_params'] = {
                'lote': lote_id,
                'fecha': ahora.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'prov': razon_social
            }
            return redirect('movimientos.historial_salidas')
        except forms.ValidationError as e:
            messages.error(request, str(e))
            return redirect('movimientos.salida')
        except Exception as e:
            messages.error(request, f'Error al procesar las salidas: {str(e)}')
            return redirect('movimientos.salida')
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_traslado_vencido_form(request):
    from ..models import UnidadEmpaqueChoices
    qs = Inventario.objects.all().order_by('nombre_producto')
    unidades_choices = UnidadEmpaqueChoices.choices
    unidades_html = "".join([f'<option value="{v}">{l}</option>' for v, l in unidades_choices])
    
    productos_json = []
    for p in qs:
        productos_json.append({
            'id': p.id_producto,
            'nombre': str(p.nombre_producto or ""),
            'codigo': str(p.codigo_producto or ""),
            'stock': p.cantidad,
            'unidades_html': unidades_html,
            'id_unidad_default': p.unidad_empaque,
            'cant_por_empaque': p.cantidad_por_empaque,
            'total_empaques': p.total_empaques
        })
    return render(request, 'movimientos/form_traslado_vencido.html', {
        'productos_json': productos_json,
        'unidades_choices': unidades_choices,
    })

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_traslado_vencido_confirmar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        cants_por_empaque = request.POST.getlist('cant_por_empaque[]')
        items_resumen = []
        for i in range(len(producto_ids)):
            cant = int(totales[i])
            if cant > 0:
                producto = Inventario.objects.get(id_producto=producto_ids[i])
                items_resumen.append({
                    'producto': producto,
                    'unidad': unidades_empaque[i],
                    'cant_por_empaque': cants_por_empaque[i] if cants_por_empaque and i < len(cants_por_empaque) else producto.cantidad_por_empaque,
                    'cant_empaques': cants_empaques[i],
                    'total': cant,
                })
        if not items_resumen:
            messages.warning(request, "Debe seleccionar al menos un producto con cantidad mayor a cero.")
            return redirect('movimientos.traslado_vencido')
        return render(request, 'movimientos/confirmar_traslado_vencido.html', {
            'items': items_resumen,
        })
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_traslado_vencido_procesar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        
        ahora = timezone.now()
        lote_id = f"TV-{ahora.strftime('%Y%m%d%H%M')}-{str(uuid.uuid4())[:8]}"
        traslados_creados = 0
        try:
            with transaction.atomic():
                for i in range(len(producto_ids)):
                    producto = Inventario.objects.get(id_producto=producto_ids[i])
                    cant_traslado = int(totales[i])
                    if cant_traslado > 0:
                        if producto.cantidad < cant_traslado:
                            raise forms.ValidationError(f"Stock insuficiente para {producto.nombre_producto}. Disponible: {producto.cantidad}")
                        
                        MovimientosInventario.objects.create(
                            producto=producto,
                            tipo_movimiento='TRASLADO_VENCIDO',
                            cantidad=cant_traslado,
                            unidad_empaque=unidades_empaque[i],
                            cantidad_empaques=float(cants_empaques[i]) if cants_empaques[i] else 0.0,
                            fecha_movimiento=ahora,
                            codigo_lote=lote_id
                        )
                        producto.cantidad -= cant_traslado
                        producto.cantidad_vencido += cant_traslado
                        producto.save()
                        traslados_creados += 1
            messages.success(request, f'Se trasladaron exitosamente {traslados_creados} productos al deposito de vencidos.')
            request.session['ultimo_vencido_pdf_lote'] = lote_id
            request.session['ultimo_vencido_pdf_tipo'] = 'TRASLADO_VENCIDO'
            return redirect('inventario.deposito_vencido')
        except forms.ValidationError as e:
            messages.error(request, str(e))
            return redirect('movimientos.traslado_vencido')
        except Exception as e:
            messages.error(request, f'Error al procesar el traslado: {str(e)}')
            return redirect('movimientos.traslado_vencido')
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_carga_vencido_form(request):
    from ..models import UnidadEmpaqueChoices
    qs = Inventario.objects.all().order_by('nombre_producto')
    unidades_choices = UnidadEmpaqueChoices.choices
    unidades_html = "".join([f'<option value="{v}">{l}</option>' for v, l in unidades_choices])
    
    productos_json = []
    for p in qs:
        productos_json.append({
            'id': p.id_producto,
            'nombre': str(p.nombre_producto or ""),
            'codigo': str(p.codigo_producto or ""),
            'stock_vencido': p.cantidad_vencido,
            'unidades_html': unidades_html,
            'id_unidad_default': p.unidad_empaque,
            'cant_por_empaque': p.cantidad_por_empaque,
        })
    return render(request, 'movimientos/form_carga_vencido.html', {
        'productos_json': productos_json,
        'unidades_choices': unidades_choices,
    })

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_carga_vencido_confirmar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        cants_por_empaque = request.POST.getlist('cant_por_empaque[]')
        items_resumen = []
        for i in range(len(producto_ids)):
            cant = int(totales[i])
            if cant > 0:
                producto = Inventario.objects.get(id_producto=producto_ids[i])
                items_resumen.append({
                    'producto': producto,
                    'unidad': unidades_empaque[i],
                    'cant_por_empaque': cants_por_empaque[i] if cants_por_empaque and i < len(cants_por_empaque) else producto.cantidad_por_empaque,
                    'cant_empaques': cants_empaques[i],
                    'total': cant,
                })
        if not items_resumen:
            messages.warning(request, "Debe seleccionar al menos un producto con cantidad mayor a cero.")
            return redirect('movimientos.carga_vencido')
        return render(request, 'movimientos/confirmar_carga_vencido.html', {
            'items': items_resumen,
        })
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_carga_vencido_procesar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        
        # Intentar obtener o crear el proveedor ficticio
        proveedor_ficticio, _ = Proveedor.objects.get_or_create(
            rif='J-00000000-0',
            defaults={
                'razonsocial': 'PISO DE VENTA (CARGA DIRECTA)',
                'direccion': 'N/A',
                'telefono': '0000'
            }
        )

        ahora = timezone.now()
        lote_id = f"CV-{ahora.strftime('%Y%m%d%H%M')}-{str(uuid.uuid4())[:8]}"
        cargas_creadas = 0
        try:
            with transaction.atomic():
                for i in range(len(producto_ids)):
                    producto = Inventario.objects.get(id_producto=producto_ids[i])
                    cant_carga = int(totales[i])
                    if cant_carga > 0:
                        MovimientosInventario.objects.create(
                            producto=producto,
                            tipo_movimiento='CARGA_VENCIDO',
                            cantidad=cant_carga,
                            unidad_empaque=unidades_empaque[i],
                            cantidad_empaques=float(cants_empaques[i]) if cants_empaques[i] else 0.0,
                            fecha_movimiento=ahora,
                            codigo_lote=lote_id,
                            proveedor=proveedor_ficticio
                        )
                        # SOLO suma al vencido, NO descuenta del principal
                        producto.cantidad_vencido += cant_carga
                        producto.save()
                        cargas_creadas += 1
            messages.success(request, f'Se cargaron exitosamente {cargas_creadas} productos directamente al deposito de vencidos.')
            request.session['ultimo_vencido_pdf_lote'] = lote_id
            request.session['ultimo_vencido_pdf_tipo'] = 'CARGA_VENCIDO'
            return redirect('inventario.deposito_vencido')
        except Exception as e:
            messages.error(request, f'Error al procesar la carga: {str(e)}')
            return redirect('movimientos.carga_vencido')
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_almacenista_o_superior, login_url='index')
def movimientos_entrada_form(request):
    from ..models import UnidadEmpaqueChoices
    unidades_choices = UnidadEmpaqueChoices.choices
    unidades_html = "".join([f'<option value="{v}">{l}</option>' for v, l in unidades_choices])
    hace_6_dias = timezone.now() - timedelta(days=6)
    rotacion_map = {
        item['producto_id']: item['total']
        for item in MovimientosInventario.objects.filter(
            tipo_movimiento='SALIDA',
            fecha_movimiento__gte=hace_6_dias
        ).values('producto_id').annotate(total=Sum('cantidad'))
    }
    qs = Inventario.objects.all().order_by('nombre_producto')
    productos_json = []
    for p in qs:
        productos_json.append({
            'id': p.id_producto,
            'nombre': str(p.nombre_producto or ""),
            'codigo': str(p.codigo_producto or ""),
            'stock': p.cantidad,
            'rotacion': rotacion_map.get(p.id_producto, 0),
            'unidades_html': unidades_html,
            'id_unidad_default': p.unidad_empaque,
            'cant_por_empaque': p.cantidad_por_empaque,
            'total_empaques': p.total_empaques
        })
    proveedores = Proveedor.objects.all().order_by('razonsocial')
    return render(request, 'movimientos/form_entrada.html', {
        'productos_json': productos_json,
        'unidades_choices': unidades_choices,
        'proveedores': proveedores,
    })

@login_required
@user_passes_test(es_almacenista_o_superior, login_url='index')
def movimientos_entrada_confirmar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        cants_por_empaque = request.POST.getlist('cant_por_empaque[]')
        proveedor_id = request.POST.get('proveedor_id')
        items_resumen = []
        for i in range(len(producto_ids)):
            cant = int(totales[i])
            if cant > 0:
                producto = Inventario.objects.get(id_producto=producto_ids[i])
                items_resumen.append({
                    'producto': producto,
                    'unidad': unidades_empaque[i],
                    'cant_por_empaque': cants_por_empaque[i] if cants_por_empaque and i < len(cants_por_empaque) else producto.cantidad_por_empaque,
                    'cant_empaques': cants_empaques[i],
                    'total': cant,
                })
        if not items_resumen:
            messages.warning(request, "Debe seleccionar al menos un producto con cantidad mayor a cero.")
            return redirect('movimientos.entrada')
        pedido_id_vincular = request.POST.get('pedido_id_vincular')
        proveedor = None
        if proveedor_id:
            proveedor = get_object_or_404(Proveedor, id=proveedor_id)
        return render(request, 'movimientos/confirmar_entrada.html', {
            'items': items_resumen,
            'proveedor': proveedor,
            'pedido_id_vincular': pedido_id_vincular
        })
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_almacenista_o_superior, login_url='index')
def movimientos_entrada_procesar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        proveedor_id = request.POST.get('proveedor_id')
        if not proveedor_id:
            messages.error(request, 'Debe seleccionar un proveedor para el ingreso.')
            return redirect('movimientos.entrada')
        proveedor = Proveedor.objects.get(id=proveedor_id)
        ahora = timezone.now()
        lote_id = f"E-{ahora.strftime('%Y%m%d%H%M')}-{str(uuid.uuid4())[:8]}"
        entradas_creadas = 0
        try:
            with transaction.atomic():
                for i in range(len(producto_ids)):
                    producto = Inventario.objects.get(id_producto=producto_ids[i])
                    cant_entrada = int(totales[i])
                    if cant_entrada > 0:
                        MovimientosInventario.objects.create(
                            producto=producto,
                            tipo_movimiento='ENTRADA',
                            cantidad=cant_entrada,
                            unidad_empaque=unidades_empaque[i],
                            cantidad_empaques=float(cants_empaques[i]) if cants_empaques[i] else 0.0,
                            proveedor=proveedor,
                            fecha_movimiento=ahora,
                            codigo_lote=lote_id
                        )
                        producto.cantidad += cant_entrada
                        producto.proveedores.add(proveedor)
                        producto.save()
                        entradas_creadas += 1
            messages.success(request, f'Se registraron exitosamente {entradas_creadas} ingresos de stock de {proveedor.razonsocial}.')
            request.session['ultimo_pdf_params'] = {
                'lote': lote_id,
                'fecha': ahora.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'prov': proveedor.razonsocial
            }
            pedido_id_input = request.POST.get('pedido_id_vincular')
            if pedido_id_input:
                try:
                    pedido_real = PedidoCompra.objects.get(id_pedido=pedido_id_input)
                    pedido_real.estado = 'COMPLETADO'
                    pedido_real.save()
                    messages.info(request, f"El pedido {pedido_real.codigo_lote} ha sido marcado como COMPLETADO.")
                except PedidoCompra.DoesNotExist:
                    pass
            return redirect('movimientos.historial_entradas')
        except Exception as e:
            messages.error(request, f'Error al procesar las entradas: {str(e)}')
            return redirect('movimientos.entrada')
    return redirect('movimientos.index')

@login_required
def movimientos_historial_vencidos_producto(request, producto_id):
    from django.core.paginator import Paginator
    from django.shortcuts import get_object_or_404
    producto = get_object_or_404(Inventario, id_producto=producto_id)
    movimientos_list = MovimientosInventario.objects.filter(
        producto=producto,
        tipo_movimiento__in=['TRASLADO_VENCIDO', 'CARGA_VENCIDO']
    ).order_by('-fecha_movimiento')
    
    paginator = Paginator(movimientos_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'movimientos/historial_vencidos_producto.html', {
        'producto': producto,
        'page_obj': page_obj,
    })

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_historial_salidas(request):
    return _historial_agrupado(request, 'SALIDA', 'Historial de Salidas')

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_historial_entradas(request):
    return _historial_agrupado(request, 'ENTRADA', 'Historial de Entradas')

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_historial_vencidos(request):
    """Historial de traslados y cargas directas al depósito de vencidos."""
    q = request.GET.get('q', '').strip()
    tipo_filtro = request.GET.get('tipo', '').strip()  # '' | 'TRASLADO_VENCIDO' | 'CARGA_VENCIDO'

    tipos_validos = ['TRASLADO_VENCIDO', 'CARGA_VENCIDO']
    if tipo_filtro in tipos_validos:
        qs = MovimientosInventario.objects.filter(tipo_movimiento=tipo_filtro).select_related('producto', 'proveedor')
    else:
        qs = MovimientosInventario.objects.filter(tipo_movimiento__in=tipos_validos).select_related('producto', 'proveedor')

    if q:
        qs = qs.filter(Q(producto__nombre_producto__icontains=q) | Q(producto__codigo_producto__icontains=q))

    from django.db.models.functions import Cast
    from django.db.models import CharField, Case, When
    qs_agrupado = qs.annotate(
        lote_final=Case(
            When(Q(codigo_lote__isnull=True) | Q(codigo_lote=''), then=Cast('id_movimiento', CharField())),
            default='codigo_lote'
        )
    )

    lotes_ids = qs_agrupado.values_list('lote_final', flat=True).distinct().order_by('-fecha_movimiento')

    paginator = Paginator(lotes_ids, 10)
    page_number = request.GET.get('page')
    lotes_page = paginator.get_page(page_number)

    historial_final = []
    for lid in lotes_page:
        if lid.isdigit() and not qs.filter(codigo_lote=lid).exists():
            movs_del_lote = qs.filter(id_movimiento=int(lid))
            es_individual = True
        else:
            movs_del_lote = qs.filter(codigo_lote=lid)
            es_individual = False

        if movs_del_lote.exists():
            primero = movs_del_lote.first()
            tipo_mov = primero.tipo_movimiento
            historial_final.append({
                'info': {
                    'codigo_lote': lid if not es_individual else 'Individual (Sin Lote)',
                    'fecha_movimiento': primero.fecha_movimiento,
                    'tipo_movimiento': tipo_mov,
                    'total_items': movs_del_lote.count(),
                    'total_unidades': movs_del_lote.aggregate(Sum('cantidad'))['cantidad__sum'],
                },
                'detalles': movs_del_lote
            })

    return render(request, 'movimientos/historial_vencidos.html', {
        'page_obj': lotes_page,
        'historial_list': historial_final,
        'tipo_filtro': tipo_filtro,
        'q': q,
        'titulo': 'Historial de Vencidos',
    })

def _historial_agrupado(request, tipo, titulo):
    q = request.GET.get('q', '').strip()
    prov_id = request.GET.get('prov', '').strip()
    
    if isinstance(tipo, list):
        qs = MovimientosInventario.objects.filter(tipo_movimiento__in=tipo).select_related('producto', 'proveedor')
    else:
        qs = MovimientosInventario.objects.filter(tipo_movimiento=tipo).select_related('producto', 'proveedor')
    
    if q:
        qs = qs.filter(Q(producto__nombre_producto__icontains=q) | Q(proveedor__razonsocial__icontains=q))
    
    if prov_id:
        qs = qs.filter(proveedor_id=prov_id)

    # Identificar lotes y movimientos individuales para mostrarlos por separado si no tienen lote
    from django.db.models.functions import Cast
    from django.db.models import CharField, Case, When
    
    qs_agrupado = qs.annotate(
        lote_final=Case(
            When(Q(codigo_lote__isnull=True) | Q(codigo_lote=''), then=Cast('id_movimiento', CharField())),
            default='codigo_lote'
        )
    )
    
    lotes_ids = qs_agrupado.values_list('lote_final', flat=True).distinct().order_by('-fecha_movimiento')
    
    paginator = Paginator(lotes_ids, 10)
    page_number = request.GET.get('page')
    lotes_page = paginator.get_page(page_number)
    
    historial_final = []
    for lid in lotes_page:
        # Si lid es un ID de movimiento (individual) o un codigo_lote real
        if lid.isdigit() and not qs.filter(codigo_lote=lid).exists():
            movs_del_lote = qs.filter(id_movimiento=int(lid))
            es_individual = True
        else:
            movs_del_lote = qs.filter(codigo_lote=lid)
            es_individual = False
            
        if movs_del_lote.exists():
            primero = movs_del_lote.first()
            info_lote = {
                'codigo_lote': lid if not es_individual else "Individual (Sin Lote)",
                'fecha_movimiento': primero.fecha_movimiento,
                'proveedor__razonsocial': primero.proveedor.razonsocial if primero.proveedor else "S/P",
                'proveedor__rif': primero.proveedor.rif if primero.proveedor else "-",
                'total_items': movs_del_lote.count(),
                'total_unidades': movs_del_lote.aggregate(Sum('cantidad'))['cantidad__sum']
            }
            historial_final.append({
                'info': info_lote,
                'detalles': movs_del_lote
            })

    proveedores_list = Proveedor.objects.all().order_by('razonsocial')
    ultimo_pdf_params = request.session.pop('ultimo_pdf_params', None)
    
    return render(request, 'movimientos/historial_masivo.html', {
        'page_obj': lotes_page,
        'historial_list': historial_final,
        'proveedores_list': proveedores_list,
        'prov_id': prov_id,
        'tipo': tipo,
        'titulo': titulo,
        'q': q,
        'modal_pdf_params': ultimo_pdf_params
    })

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def historial_proveedores_notas_index(request):
    base_qs = MovimientosInventario.objects.all()
    q = request.GET.get('q', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    order = request.GET.get('order', 'desc')
    if q:
        base_qs = base_qs.filter(
            Q(producto__nombre_producto__icontains=q) |
            Q(proveedor__razonsocial__icontains=q) |
            Q(tipo_movimiento__icontains=q)
        )
    if date_from:
        try:
            fecha_inicio = datetime.strptime(date_from, '%Y-%m-%d')
            base_qs = base_qs.filter(fecha_movimiento__gte=fecha_inicio)
        except ValueError:
            pass
    if date_to:
        try:
            fecha_fin = datetime.strptime(date_to, '%Y-%m-%d')
            fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
            base_qs = base_qs.filter(fecha_movimiento__lte=fecha_fin)
        except ValueError:
            pass
    qs = base_qs.values(
        'proveedor__razonsocial',
        'proveedor__nombre',
        'producto__nombre_producto',
        'tipo_movimiento'
    ).annotate(
        total_unidades=Sum('cantidad'),
        total_empaques=Sum('cantidad_empaques'),
        ultima_fecha=Max('fecha_movimiento')
    )
    if order == 'asc':
        qs = qs.order_by('ultima_fecha')
    else:
        qs = qs.order_by('-ultima_fecha')
    page_size = 10
    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    context = {
        'page_obj': page_obj,
        'q': q,
        'date_from': date_from,
        'date_to': date_to,
        'order': order,
    }
    return render(request, 'HistorialProveedoresNotas/index.html', context)

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def historial_proveedores_notas_crear(request):
    formulario_nota = HistorialProveedoresNotasForm(request.POST or None)
    if formulario_nota.is_valid():
        formulario_nota.save()
        messages.success(request, 'Nota registrada exitosamente.')
        return redirect('HistorialProveedoresNotas.index')
    return render(request, 'HistorialProveedoresNotas/crear.html', {'formulario_nota': formulario_nota})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def historial_proveedores_notas_editar(request,id_historialproveedor):
    nota = HistorialProveedoresNotas.objects.get(id_historialproveedor=id_historialproveedor)
    formulario_nota = HistorialProveedoresNotasForm(request.POST or None, instance=nota)
    if formulario_nota.is_valid() and request.POST:
        formulario_nota.save()
        messages.success(request, 'Nota actualizada exitosamente.')
        return redirect('HistorialProveedoresNotas.index')
    return render(request, 'HistorialProveedoresNotas/editar.html', {
        'formulario_nota': formulario_nota,
    })

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def historial_proveedores_notas_eliminar(request,id_historialproveedor):
    nota = HistorialProveedoresNotas.objects.get(id_historialproveedor=id_historialproveedor)
    nota.delete()
    messages.success(request, 'Nota eliminada exitosamente.')
    return redirect('HistorialProveedoresNotas.index')

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def exportar_lote_pdf(request):
    fecha_str = request.GET.get('fecha')
    prov_nombre = request.GET.get('prov')
    tipo = request.GET.get('tipo', 'ENTRADA')
    lote_id = request.GET.get('lote')
    
    try:
        from fpdf import FPDF
        if lote_id:
            qs = MovimientosInventario.objects.filter(codigo_lote=lote_id).select_related('producto', 'proveedor')
        else:
            filtros = {
                'fecha_movimiento': fecha_str,
                'tipo_movimiento': tipo,
            }
            if prov_nombre:
                filtros['proveedor__razonsocial'] = prov_nombre
            qs = MovimientosInventario.objects.filter(**filtros).select_related('producto', 'proveedor')
        
        if not qs.exists():
            messages.error(request, "No se encontró el lote especificado.")
            return redirect('movimientos.index')
            
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        
        titulo_doc = "COMPROBANTE ENTRADA" if tipo == 'ENTRADA' else "Comprobante de Salida"
        pdf.cell(0, 10, titulo_doc, ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 10, f"Fecha: {timezone.localtime(qs[0].fecha_movimiento).strftime('%d/%m/%Y %H:%M:%S')}", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Datos del Proveedor / Destinatario:", ln=True)
        pdf.set_font("Helvetica", "", 11)
        proveedor = qs[0].proveedor
        nombre_prov = proveedor.razonsocial if proveedor else "Sin proveedor asignado"
        rif_prov = proveedor.rif if proveedor else "N/A"
        pdf.cell(0, 7, f"Nombre/Razon Social: {nombre_prov}", ln=True)
        pdf.cell(0, 7, f"RIF: {rif_prov}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(90, 10, "Producto", 1, 0, "C", True)
        pdf.cell(25, 10, "Total Unid.", 1, 0, "C", True)
        pdf.cell(25, 10, "Unidad", 1, 0, "C", True)
        pdf.cell(25, 10, "U. x Req.", 1, 0, "C", True)
        pdf.cell(25, 10, "Requerimiento", 1, 1, "C", True)
        
        pdf.set_font("Helvetica", "", 8)
        for item in qs:
            pdf.cell(90, 8, item.producto.nombre_producto[:45], 1, 0, "L")
            pdf.cell(25, 8, str(item.cantidad), 1, 0, "C")
            pdf.cell(25, 8, str(item.unidad_empaque), 1, 0, "C")
            pdf.cell(25, 8, str(item.producto.cantidad_por_empaque), 1, 0, "C")
            pdf.cell(25, 8, str(item.cantidad_empaques), 1, 1, "C")
        
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 10, "Documento generado automaticamente por el sistema de inventario.", ln=True, align="R")
        
        from django.http import HttpResponse
        pdf_out = pdf.output(dest='S')
        if isinstance(pdf_out, str):
            pdf_out = pdf_out.encode('latin-1')
        else:
            pdf_out = bytes(pdf_out)
        response = HttpResponse(pdf_out, content_type='application/pdf')
        filename = f"comprobante_{tipo.lower()}_{qs[0].fecha_movimiento.strftime('%Y%m%d_%H%M%S')}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
        
    except Exception as e:
        messages.error(request, f"Error al generar el PDF: {str(e)}")
        return redirect('movimientos.index')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_lote_eliminar(request):
    if request.method == 'POST':
        lote_id = request.POST.get('lote_id')
        fecha_str = request.POST.get('fecha')
        prov_nombre = request.POST.get('prov')
        tipo = request.POST.get('tipo', 'ENTRADA')

        try:
            with transaction.atomic():
                if lote_id:
                    movs = MovimientosInventario.objects.filter(codigo_lote=lote_id).select_related('producto')
                else:
                    movs = MovimientosInventario.objects.filter(
                        fecha_movimiento=fecha_str,
                        proveedor__razonsocial=prov_nombre,
                        tipo_movimiento=tipo
                    ).select_related('producto')

                count = 0
                for mov in movs:
                    producto = mov.producto
                    if mov.tipo_movimiento == 'ENTRADA':
                        producto.cantidad -= mov.cantidad
                    elif mov.tipo_movimiento == 'SALIDA':
                        producto.cantidad += mov.cantidad
                    producto.save()
                    count += 1
                
                movs.delete()
                
            messages.success(request, f'Lote eliminado exitosamente ({count} registros revertidos).')
            
        except Exception as e:
            messages.error(request, f'Error al eliminar el lote: {str(e)}')
            
        return redirect(request.META.get('HTTP_REFERER', 'movimientos.index'))
    return redirect('movimientos.index')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_lote_editar(request, lote_id):
    movimientos = MovimientosInventario.objects.filter(codigo_lote=lote_id).select_related('producto', 'proveedor')
    if not movimientos.exists():
        messages.error(request, "Lote no encontrado.")
        return redirect('movimientos.index')

    tipo = movimientos.first().tipo_movimiento

    if request.method == 'POST':
        try:
            with transaction.atomic():
                cambios = 0
                eliminados = 0
                for mov in movimientos:
                    nueva_cantidad = request.POST.get(f'cantidad_{mov.id_movimiento}')
                    nueva_unidad = request.POST.get(f'unidad_{mov.id_movimiento}')
                    nueva_cant_por_empaque = request.POST.get(f'cant_por_empaque_{mov.id_movimiento}')
                    
                    if nueva_cantidad and str(nueva_cantidad).isdigit():
                        nueva_cantidad = int(nueva_cantidad)
                        if nueva_cantidad == 0:
                            producto = mov.producto
                            if mov.tipo_movimiento == 'ENTRADA':
                                producto.cantidad -= mov.cantidad
                            elif mov.tipo_movimiento == 'SALIDA':
                                producto.cantidad += mov.cantidad
                            producto.save()
                            mov.delete()
                            eliminados += 1
                            continue

                        nueva_cant_empaques = nueva_cantidad
                        if nueva_cant_por_empaque and str(nueva_cant_por_empaque).isdigit() and int(nueva_cant_por_empaque) > 0:
                            nueva_cant_por_empaque_int = int(nueva_cant_por_empaque)
                            nueva_cant_empaques = round(nueva_cantidad / float(nueva_cant_por_empaque_int), 2)

                        if nueva_cantidad != mov.cantidad or nueva_unidad != mov.unidad_empaque or nueva_cant_empaques != mov.cantidad_empaques:
                            producto = mov.producto
                            if tipo == 'SALIDA' and nueva_cantidad > mov.cantidad:
                                diff = nueva_cantidad - mov.cantidad
                                if producto.cantidad < diff:
                                    raise Exception(f"Stock insuficiente para {producto.nombre_producto}. Faltan {diff - producto.cantidad} unid.")
                            if mov.tipo_movimiento == 'ENTRADA':
                                producto.cantidad -= mov.cantidad
                            elif mov.tipo_movimiento == 'SALIDA':
                                producto.cantidad += mov.cantidad
                            if mov.tipo_movimiento == 'ENTRADA':
                                producto.cantidad += nueva_cantidad
                            elif mov.tipo_movimiento == 'SALIDA':
                                producto.cantidad -= nueva_cantidad
                            producto.save()
                            mov.cantidad = nueva_cantidad
                            mov.cantidad_empaques = nueva_cant_empaques
                            mov.unidad_empaque = nueva_unidad
                            mov.save()
                            cambios += 1
                            
                nuevos_prods_ids = request.POST.getlist('nuevo_producto_id[]')
                nuevas_cantidades = request.POST.getlist('nueva_cantidad_prod[]')
                nuevas_unidades = request.POST.getlist('nueva_unidad_prod[]')
                nuevas_cants_por_empaque = request.POST.getlist('nueva_cant_por_empaque_prod[]')
                nuevos_agregados = 0
                for i in range(len(nuevos_prods_ids)):
                    nuevo_prod_id = nuevos_prods_ids[i]
                    nueva_cant_prod = nuevas_cantidades[i] if i < len(nuevas_cantidades) else ''
                    nueva_unidad_prod = nuevas_unidades[i] if i < len(nuevas_unidades) else ''
                    nueva_cant_por_empaque_prod = nuevas_cants_por_empaque[i] if i < len(nuevas_cants_por_empaque) else ''
                    if nuevo_prod_id and nueva_cant_prod and str(nueva_cant_prod).isdigit():
                        nueva_cant_prod = int(nueva_cant_prod)
                        nueva_cant_empaques_prod = nueva_cant_prod
                        if nueva_cant_por_empaque_prod and str(nueva_cant_por_empaque_prod).isdigit() and int(nueva_cant_por_empaque_prod) > 0:
                            nueva_cant_empaques_prod = round(nueva_cant_prod / float(nueva_cant_por_empaque_prod), 2)
                            
                        if nueva_cant_prod > 0:
                            prod_nuevo = Inventario.objects.get(id_producto=nuevo_prod_id)
                            info = movimientos.first()
                            if tipo == 'SALIDA' and prod_nuevo.cantidad < nueva_cant_prod:
                                raise Exception(f"Stock insuficiente para {prod_nuevo.nombre_producto}. Disponibles: {prod_nuevo.cantidad}")
                            if tipo == 'ENTRADA':
                                prod_nuevo.cantidad += nueva_cant_prod
                            elif tipo == 'SALIDA':
                                prod_nuevo.cantidad -= nueva_cant_prod
                            prod_nuevo.save()
                            MovimientosInventario.objects.create(
                                producto=prod_nuevo,
                                tipo_movimiento=tipo,
                                cantidad=nueva_cant_prod,
                                unidad_empaque=nueva_unidad_prod,
                                cantidad_empaques=nueva_cant_empaques_prod,
                                proveedor=info.proveedor,
                                fecha_movimiento=info.fecha_movimiento,
                                codigo_lote=lote_id
                            )
                            nuevos_agregados += 1
                msg = f"Lote actualizado correctamente. {cambios} modificados."
                if eliminados > 0: msg += f" {eliminados} eliminados."
                if nuevos_agregados > 0: msg += f" {nuevos_agregados} agregados."
                messages.success(request, msg)
                return redirect('movimientos.historial_entradas' if tipo == 'ENTRADA' else 'movimientos.historial_salidas')
        except Exception as e:
            messages.error(request, f"Error al actualizar lote: {str(e)}")

    from ..models import UnidadEmpaqueChoices
    info = movimientos.first()
    # Mostramos todos los productos para que siempre se pueda agregar un extra
    productos_disponibles = Inventario.objects.all().order_by('nombre_producto')
    productos_en_lote = movimientos.values_list('producto_id', flat=True)
    productos_disponibles = productos_disponibles.exclude(id_producto__in=productos_en_lote)

    return render(request, 'movimientos/lote_editar.html', {
        'movimientos': movimientos,
        'lote_id': lote_id,
        'tipo': tipo,
        'info': info,
        'unidades_choices': UnidadEmpaqueChoices.choices,
        'productos_disponibles': productos_disponibles
    })


@login_required
@user_passes_test(es_almacenista_o_superior, login_url='index')
def exportar_vencido_pdf(request):
    """Genera PDF para traslado a vencidos o carga directa a vencidos."""
    lote_id = request.GET.get('lote')
    tipo = request.GET.get('tipo', 'TRASLADO_VENCIDO')

    try:
        from fpdf import FPDF
        from django.http import HttpResponse

        qs = MovimientosInventario.objects.filter(
            codigo_lote=lote_id
        ).select_related('producto', 'proveedor').order_by('id_movimiento')

        if not qs.exists():
            messages.error(request, 'No se encontro el lote especificado para generar el PDF.')
            return redirect('inventario.deposito_vencido')

        ahora = timezone.localtime(qs[0].fecha_movimiento)

        if tipo == 'TRASLADO_VENCIDO':
            titulo_doc = 'COMPROBANTE DE TRASLADO A VENCIDOS'
            subtitulo = 'Traslado desde inventario principal al deposito de vencidos'
        else:
            titulo_doc = 'COMPROBANTE DE CARGA DIRECTA A VENCIDOS'
            subtitulo = 'Carga directa de productos al deposito de vencidos'

        pdf = FPDF()
        pdf.add_page()

        # Encabezado
        pdf.set_font('Helvetica', 'B', 13)
        pdf.cell(0, 10, titulo_doc, ln=True, align='C')
        pdf.set_font('Helvetica', '', 8)
        pdf.cell(0, 5, subtitulo, ln=True, align='C')
        pdf.cell(0, 5, f'Fecha: {ahora.strftime("%d/%m/%Y %H:%M:%S")}', ln=True, align='C')
        pdf.cell(0, 5, f'Codigo de Lote: {lote_id}', ln=True, align='C')
        pdf.ln(6)

        # Separador
        pdf.set_draw_color(200, 200, 200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

        # Tabla header
        pdf.set_font('Helvetica', 'B', 7)
        pdf.set_fill_color(50, 50, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(35, 8, 'Codigo', 1, 0, 'C', True)
        pdf.cell(65, 8, 'Producto', 1, 0, 'C', True)
        pdf.cell(25, 8, 'Cant. Unidades', 1, 0, 'C', True)
        pdf.cell(25, 8, 'U. x Empaque', 1, 0, 'C', True)
        pdf.cell(40, 8, 'Total Empaques', 1, 1, 'C', True)

        pdf.set_font('Helvetica', '', 7)
        pdf.set_text_color(0, 0, 0)
        fill = False
        total_unidades = 0
        for mov in qs:
            pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
            nombre = (mov.producto.nombre_producto or '')[:38]
            codigo = (mov.producto.codigo_producto or '')
            cant_por_emp = mov.producto.cantidad_por_empaque or 1
            empaques = round(mov.cantidad / cant_por_emp, 2)
            pdf.cell(35, 7, str(codigo), 1, 0, 'L', fill)
            pdf.cell(65, 7, nombre, 1, 0, 'L', fill)
            pdf.cell(25, 7, str(mov.cantidad), 1, 0, 'C', fill)
            pdf.cell(25, 7, str(cant_por_emp), 1, 0, 'C', fill)
            pdf.cell(40, 7, str(empaques), 1, 1, 'C', fill)
            total_unidades += mov.cantidad
            fill = not fill

        # Totales
        pdf.ln(4)
        pdf.set_font('Helvetica', 'B', 8)
        pdf.cell(0, 7, f'Total de productos registrados: {qs.count()}', ln=True)
        pdf.cell(0, 7, f'Total de unidades afectadas: {total_unidades}', ln=True)

        pdf.ln(8)
        pdf.set_font('Helvetica', 'I', 7)
        pdf.cell(0, 5, 'Documento generado automaticamente por el sistema de inventario.', ln=True, align='R')

        pdf_out = pdf.output(dest='S')
        if isinstance(pdf_out, str):
            pdf_out = pdf_out.encode('latin-1')
        else:
            pdf_out = bytes(pdf_out)

        response = HttpResponse(pdf_out, content_type='application/pdf')
        tipo_str = 'traslado_vencido' if tipo == 'TRASLADO_VENCIDO' else 'carga_vencido'
        filename = f'comprobante_{tipo_str}_{ahora.strftime("%Y%m%d_%H%M%S")}.pdf'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        messages.error(request, f'Error al generar el PDF: {str(e)}')
        return redirect('inventario.deposito_vencido')

