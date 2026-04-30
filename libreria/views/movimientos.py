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
from .auth import es_inventario_acceso, es_pleno_acceso
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
        resumen_por_producto = qs.values('producto__nombre_producto') \
                                 .annotate(
                                     entradas=Sum('cantidad', default=0, filter=Q(tipo_movimiento='ENTRADA')),
                                     salidas=Sum('cantidad', default=0, filter=Q(tipo_movimiento='SALIDA'))
                                 ).order_by('producto__nombre_producto')
        
        entradas_str_parts = []
        salidas_str_parts = []
        total_entradas_general = 0
        total_salidas_general = 0

        for item in resumen_por_producto:
            if item['entradas'] and item['entradas'] > 0:
                entradas_str_parts.append(f"{item['entradas']} ({item['producto__nombre_producto']})")
                total_entradas_general += item['entradas']
            if item['salidas'] and item['salidas'] > 0:
                salidas_str_parts.append(f"{item['salidas']} ({item['producto__nombre_producto']})")
                total_salidas_general += item['salidas']

        ids_productos = qs.values_list('producto_id', flat=True).distinct()
        productos_stock = Inventario.objects.filter(id_producto__in=ids_productos).values('nombre_producto', 'cantidad').order_by('nombre_producto')
        
        stock_desglose = []
        total_stock_general = 0
        for p in productos_stock:
            stock_desglose.append(f"{p['cantidad']} ({p['nombre_producto']})")
            total_stock_general += p['cantidad']

        resumen_filtro = {
            'entradas_desglose': entradas_str_parts,
            'salidas_desglose': salidas_str_parts,
            'stock_desglose': stock_desglose,
            'total_entradas_general': total_entradas_general,
            'total_salidas_general': total_salidas_general,
            'stock_actual': total_stock_general
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
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_salida_form(request):
    from ..models import UnidadEmpaqueChoices
    qs = Inventario.objects.all().order_by('nombre_producto')
    unidades_choices = UnidadEmpaqueChoices.choices
    unidades_html = "".join([f'<option value="{v}">{l}</option>' for v, l in unidades_choices])
    hace_30_dias = timezone.now() - timedelta(days=30)
    rotacion_map = {
        item['producto_id']: item['total']
        for item in MovimientosInventario.objects.filter(
            tipo_movimiento='SALIDA',
            fecha_movimiento__gte=hace_30_dias
        ).values('producto_id').annotate(total=Sum('cantidad'))
    }
    productos_json = []
    for p in qs:
        productos_json.append({
            'id': p.id_producto,
            'nombre': p.nombre_producto,
            'codigo': p.codigo_producto,
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
@user_passes_test(es_pleno_acceso, login_url='index')
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
@user_passes_test(es_pleno_acceso, login_url='index')
def movimientos_salida_procesar(request):
    if request.method == 'POST':
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        proveedor_id = request.POST.get('proveedor_id')
        if not proveedor_id:
            messages.error(request, 'Debe seleccionar un proveedor para el descargo.')
            return redirect('movimientos.salida')
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
                            cantidad_empaques=int(float(cants_empaques[i])) if cants_empaques[i] else 0,
                            proveedor=proveedor,
                            fecha_movimiento=ahora,
                            codigo_lote=lote_id
                        )
                        producto.cantidad -= cant_salida
                        producto.save()
                        salidas_creadas += 1
            messages.success(request, f'Se registraron exitosamente {salidas_creadas} salidas del inventario con descargo a {proveedor.razonsocial}.')
            request.session['ultimo_pdf_params'] = {
                'lote': lote_id,
                'fecha': ahora.strftime('%Y-%m-%d %H:%M:%S.%f'),
                'prov': proveedor.razonsocial
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
def movimientos_entrada_form(request):
    from ..models import UnidadEmpaqueChoices
    unidades_choices = UnidadEmpaqueChoices.choices
    unidades_html = "".join([f'<option value="{v}">{l}</option>' for v, l in unidades_choices])
    hace_30_dias = timezone.now() - timedelta(days=30)
    rotacion_map = {
        item['producto_id']: item['total']
        for item in MovimientosInventario.objects.filter(
            tipo_movimiento='SALIDA',
            fecha_movimiento__gte=hace_30_dias
        ).values('producto_id').annotate(total=Sum('cantidad'))
    }
    qs = Inventario.objects.all().order_by('nombre_producto')
    productos_json = []
    for p in qs:
        productos_json.append({
            'id': p.id_producto,
            'nombre': p.nombre_producto,
            'codigo': p.codigo_producto,
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
@user_passes_test(es_pleno_acceso, login_url='index')
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
@user_passes_test(es_pleno_acceso, login_url='index')
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
                            cantidad_empaques=int(float(cants_empaques[i])) if cants_empaques[i] else 0,
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
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_historial_salidas(request):
    return _historial_agrupado(request, 'SALIDA', 'Historial de Salidas')

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_historial_entradas(request):
    return _historial_agrupado(request, 'ENTRADA', 'Historial de Entradas')

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
            qs = MovimientosInventario.objects.filter(
                fecha_movimiento=fecha_str,
                proveedor__razonsocial=prov_nombre,
                tipo_movimiento=tipo
            ).select_related('producto', 'proveedor')
        
        if not qs.exists():
            messages.error(request, "No se encontró el lote especificado.")
            return redirect('movimientos.index')
            
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        
        titulo_doc = "COMPROBANTE ENTRADA" if tipo == 'ENTRADA' else "Comprobante de Salida"
        pdf.cell(0, 10, titulo_doc, ln=True, align="C")
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 10, f"Fecha: {qs[0].fecha_movimiento.strftime('%d/%m/%Y %H:%M:%S')}", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 10, "Datos del Proveedor / Destinatario:", ln=True)
        pdf.set_font("Helvetica", "", 11)
        pdf.cell(0, 7, f"Nombre/Razon Social: {qs[0].proveedor.razonsocial}", ln=True)
        pdf.cell(0, 7, f"RIF: {qs[0].proveedor.rif}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(240, 240, 240)
        pdf.cell(70, 10, "Producto", 1, 0, "C", True)
        pdf.cell(30, 10, "Total Unid.", 1, 0, "C", True)
        pdf.cell(30, 10, "Unidad", 1, 0, "C", True)
        pdf.cell(30, 10, "U. x Emp.", 1, 0, "C", True)
        pdf.cell(30, 10, "Cant. Emp.", 1, 1, "C", True)
        
        pdf.set_font("Helvetica", "", 10)
        for item in qs:
            pdf.cell(70, 8, item.producto.nombre_producto[:35], 1, 0, "L")
            pdf.cell(30, 8, str(item.cantidad), 1, 0, "C")
            pdf.cell(30, 8, str(item.unidad_empaque), 1, 0, "C")
            pdf.cell(30, 8, str(item.producto.cantidad_por_empaque), 1, 0, "C")
            pdf.cell(30, 8, str(item.cantidad_empaques), 1, 1, "C")
        
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 10, "Documento generado automaticamente por el sistema de inventario.", ln=True, align="R")
        
        from django.http import HttpResponse
        response = HttpResponse(pdf.output(dest='S').encode('latin-1'), content_type='application/pdf')
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
                            nueva_cant_empaques = int(nueva_cantidad / float(nueva_cant_por_empaque_int))

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
                            nueva_cant_empaques_prod = int(nueva_cant_prod / float(nueva_cant_por_empaque_prod))
                            
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
