import uuid
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, F
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.db import transaction
from django.http import HttpResponse
from fpdf import FPDF
from .auth import es_admin, es_gestion_pedidos, es_pleno_acceso, es_inventario_acceso, es_soporte
from ..models import Proveedor, Inventario, PedidoCompra, DetallePedidoCompra

@login_required
@user_passes_test(es_gestion_pedidos, login_url='index')
def compras_seleccionar_proveedor(request):
    q = request.GET.get('q', '').strip()
    qs = Proveedor.objects.all()
    if q:
        qs = qs.filter(Q(razonsocial__icontains=q) | Q(rif__icontains=q))
    return render(request, 'compras/seleccionar_proveedor.html', {
        'proveedores': qs,
        'q': q
    })

@login_required
@user_passes_test(es_gestion_pedidos, login_url='index')
def compras_form_pedido(request, proveedor_id):
    proveedor = get_object_or_404(Proveedor, id=proveedor_id)
    productos = Inventario.objects.filter(proveedores__id=proveedor_id).order_by('nombre_producto')
    from ..models import UnidadEmpaqueChoices
    unidades_choices = UnidadEmpaqueChoices.choices
    return render(request, 'compras/form_pedido.html', {
        'proveedor': proveedor,
        'productos': productos,
        'productos_con_detalles': [{'producto': p, 'detalle': None} for p in productos],
        'unidades_choices': unidades_choices
    })

@login_required
@user_passes_test(es_gestion_pedidos, login_url='index')
def compras_confirmar(request):
    if request.method == 'POST':
        proveedor_id = request.POST.get('proveedor_id')
        proveedor = get_object_or_404(Proveedor, id=proveedor_id)
        producto_ids = request.POST.getlist('producto_id[]')
        items_seleccionados = request.POST.getlist('items_seleccionados[]')
        minimos = request.POST.getlist('minimo[]')
        maximos = request.POST.getlist('maximo[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        cants_por_empaque = request.POST.getlist('cant_por_empaque[]')
        pedido_id = request.POST.get('pedido_id')
        items_resumen = []
        for i in range(len(producto_ids)):
            p_id = producto_ids[i]
            if p_id in items_seleccionados:
                producto = Inventario.objects.get(id_producto=p_id)
                items_resumen.append({
                    'producto': producto,
                    'min': minimos[i],
                    'max': maximos[i],
                    'unidad': unidades_empaque[i],
                    'cant_empaques': cants_empaques[i],
                    'total': totales[i],
                    'cant_por_empaque': cants_por_empaque[i],
                })
        if not items_resumen:
            messages.warning(request, "Debe seleccionar al menos un producto para el registro.")
            return redirect('compras.nuevo', proveedor_id=proveedor_id)
        return render(request, 'compras/confirmar_pedido.html', {
            'proveedor': proveedor,
            'items': items_resumen,
            'pedido_id': pedido_id
        })
    return redirect('compras.index')

@login_required
@user_passes_test(es_gestion_pedidos, login_url='index')
def compras_procesar(request):
    if request.method == 'POST':
        proveedor_id = request.POST.get('proveedor_id')
        proveedor = get_object_or_404(Proveedor, id=proveedor_id)
        producto_ids = request.POST.getlist('producto_id[]')
        unidades_empaque = request.POST.getlist('unidad_empaque[]')
        cants_empaques = request.POST.getlist('cant_empaques[]')
        totales = request.POST.getlist('total_unidades[]')
        cants_por_empaque = request.POST.getlist('cant_por_empaque[]')
        minimos = request.POST.getlist('minimo[]')
        maximos = request.POST.getlist('maximo[]')
        pedido_id = request.POST.get('pedido_id')
        ahora = timezone.now()
        lote_id = f"E-{ahora.strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
        ordenes_creadas = 0
        try:
            with transaction.atomic():
                if pedido_id:
                    pedido = get_object_or_404(PedidoCompra, id_pedido=pedido_id)
                    pedido.detalles.all().delete()
                    pedido.save()
                else:
                    pedido = PedidoCompra.objects.create(
                        proveedor=proveedor,
                        fecha_pedido=ahora,
                        estado='PENDIENTE',
                        codigo_lote=lote_id
                    )
                for i in range(len(producto_ids)):
                    producto = Inventario.objects.get(id_producto=producto_ids[i])
                    try:
                        if i < len(minimos): producto.stock_minimo = int(minimos[i])
                        if i < len(maximos): producto.stock_maximo = int(maximos[i])
                        producto.save()
                    except:
                        pass
                    cant_pedir = int(totales[i])
                    if cant_pedir > 0:
                        DetallePedidoCompra.objects.create(
                            pedido=pedido,
                            producto=producto,
                            cantidad=cant_pedir,
                            unidad_empaque=unidades_empaque[i],
                            cantidad_empaques=int(cants_empaques[i]),
                            cantidad_por_empaque=int(cants_por_empaque[i])
                        )
                        ordenes_creadas += 1
            messages.success(request, f'Entrada procesada exitosamente. Se registraron {ordenes_creadas} productos.')
            request.session['ultimo_pedido_id'] = pedido.id_pedido
            return redirect('movimientos.historial_pedidos')
        except Exception as e:
            messages.error(request, f'Error al procesar la entrada: {str(e)}')
            return redirect('compras.nuevo', proveedor_id=proveedor_id)
    return redirect('compras.index')

@login_required
@user_passes_test(es_gestion_pedidos, login_url='index')
def compras_editar_pedido(request, pedido_id):
    pedido = get_object_or_404(PedidoCompra, id_pedido=pedido_id)
    proveedor = pedido.proveedor
    productos = Inventario.objects.filter(proveedores__id=proveedor.id).order_by('nombre_producto')
    from ..models import UnidadEmpaqueChoices
    unidades_choices = UnidadEmpaqueChoices.choices
    detalles_dict = {d.producto_id: d for d in pedido.detalles.all()}
    productos_con_detalles = []
    for p in productos:
        productos_con_detalles.append({
            'producto': p,
            'detalle': detalles_dict.get(p.id_producto)
        })
    return render(request, 'compras/form_pedido.html', {
        'proveedor': proveedor,
        'productos_con_detalles': productos_con_detalles,
        'unidades_choices': unidades_choices,
        'pedido': pedido
    })

@login_required
@user_passes_test(es_gestion_pedidos, login_url='index')
def exportar_pedido_unico_pdf(request, pedido_id):
    pedido = get_object_or_404(PedidoCompra, id_pedido=pedido_id)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 15, "COMPROBANTE ENTRADA", ln=True, align="C")
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, f"Código: {pedido.codigo_lote}", ln=True, align="C")
    pdf.ln(5)
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(95, 10, " Proveedor:", 0, 0, "L", True)
    pdf.cell(95, 10, " Detalles:", 0, 1, "L", True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(95, 7, f" {pedido.proveedor.razonsocial}", 0, 0)
    pdf.cell(95, 7, f" Fecha: {pedido.fecha_pedido.strftime('%d/%m/%Y %H:%M')}", 0, 1)
    pdf.cell(95, 7, f" RIF: {pedido.proveedor.rif}", 0, 1)
    pdf.ln(10)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(0, 123, 255)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(80, 10, " Producto", 1, 0, "L", True)
    pdf.cell(35, 10, " Empaques", 1, 0, "C", True)
    pdf.cell(35, 10, " Tipo", 1, 0, "C", True)
    pdf.cell(40, 10, " Total Unid.", 1, 1, "C", True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    for det in pedido.detalles.all():
        pdf.cell(80, 10, f" {det.producto.nombre_producto[:35]}", 1, 0, "L")
        pdf.cell(35, 10, str(det.cantidad_empaques), 1, 0, "C")
        pdf.cell(35, 10, str(det.unidad_empaque), 1, 0, "C")
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(40, 10, str(det.cantidad), 1, 1, "C")
        pdf.set_font("Helvetica", "", 10)
    pdf.ln(15)
    pdf.set_font("Helvetica", "I", 9)
    pdf.cell(0, 10, "Nota: Este documento es un comprobante de entrada de productos.", ln=True, align="C")
    response = HttpResponse(pdf.output(dest='S').encode('latin-1'), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="comprobante_entrada_{pedido.codigo_lote}.pdf"'
    return response

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def exportar_pedido_pdf(request):
    productos = Inventario.objects.filter(cantidad__lte=F('stock_minimo')).order_by('nombre_producto')
    fecha_emision = timezone.now().strftime('%d/%m/%Y %H:%M')
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "Reporte de Sugerencia de Inventario (Stock Bajo)", ln=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, f"Generado el: {fecha_emision}", ln=True, align="C")
    pdf.ln(5)
    if not productos.exists():
        pdf.set_font("Helvetica", "I", 12)
        pdf.cell(0, 20, "No hay productos con stock bajo actualmente.", ln=True, align="C")
    else:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_fill_color(220, 53, 69)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(70, 10, "Producto", 1, 0, "C", True)
        pdf.cell(30, 10, "Stock Act.", 1, 0, "C", True)
        pdf.cell(30, 10, "Stock Min.", 1, 0, "C", True)
        pdf.cell(60, 10, "Ingreso Sugerido", 1, 1, "C", True)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(0, 0, 0)
        for p in productos:
            sugerido = p.stock_maximo - p.cantidad
            if sugerido < 0: sugerido = 0
            pdf.cell(70, 10, p.nombre_producto[:35], 1, 0, "L")
            pdf.cell(30, 10, str(p.cantidad), 1, 0, "C")
            pdf.cell(30, 10, str(p.stock_minimo), 1, 0, "C")
            pdf.cell(60, 10, f"Ingresar {sugerido} unid. aprox.", 1, 1, "R")
    response = HttpResponse(pdf.output(dest='S').encode('latin-1'), content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="reporte_sugerencia_ingreso.pdf"'
    return response

@login_required
@user_passes_test(es_inventario_acceso, login_url='index')
def movimientos_historial_pedidos(request):
    q = request.GET.get('q', '').strip()
    qs = PedidoCompra.objects.select_related('proveedor').all()
    if q:
        qs = qs.filter(Q(proveedor__razonsocial__icontains=q) | Q(codigo_lote__icontains=q))
    qs = qs.prefetch_related('detalles__producto').order_by('-fecha_pedido')
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    ultimo_pedido_id = request.session.pop('ultimo_pedido_id', None)
    return render(request, 'compras/historial_pedidos.html', {
        'page_obj': page_obj,
        'titulo': 'Historial de Entradas de Productos',
        'q': q,
        'modal_pdf_id': ultimo_pedido_id
    })

@login_required
@user_passes_test(es_gestion_pedidos, login_url='index')
def compras_eliminar_pedido(request):
    if request.method == 'POST':
        pedido_id = request.POST.get('pedido_id')
        try:
            pedido = PedidoCompra.objects.get(id_pedido=pedido_id)
            pedido.delete()
            messages.success(request, 'Registro eliminado exitosamente.')
        except Exception as e:
            messages.error(request, f'Error al eliminar el registro: {str(e)}')
    return redirect('movimientos.historial_pedidos')

@login_required
@user_passes_test(es_soporte, login_url='index')
def compras_eliminar_todo_historial(request):
    if request.method == 'POST':
        try:
            cantidad = PedidoCompra.objects.count()
            PedidoCompra.objects.all().delete()
            messages.success(request, f'Se han eliminado correctamente {cantidad} registros del historial.')
        except Exception as e:
            messages.error(request, f'Error al limpiar el historial: {str(e)}')
    return redirect('movimientos.historial_pedidos')
