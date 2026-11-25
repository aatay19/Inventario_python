import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.files.storage import default_storage
from fpdf import FPDF
from libreria.views.auth import eliminar_permitido
from ..models import Evento, ProductoParque, ComboParque, Brazalete, DetalleEvento, ProductoEnCombo
from ..forms import (
    EventoForm, ProductoParqueForm, ComboParqueForm, BrazaleteForm,
    Abono2Form, ComprobanteAbono1Form,
)

CAMPOS_IMAGENES = (
    'foto_abono1', 'foto_factura_abono1', 'foto_abono2', 'foto_factura_abono2',
)


def _nombres_imagenes(evento, campos=CAMPOS_IMAGENES):
    """Captura los nombres de archivo antes de que el formulario sobrescriba los campos."""
    return {
        campo: getattr(evento, campo).name
        for campo in campos
        if getattr(evento, campo, None)
    }


def _limpiar_imagenes_reemplazadas(evento, nombres_anteriores):
    """Elimina del almacenamiento las imágenes reemplazadas o borradas."""
    for campo, nombre in nombres_anteriores.items():
        archivo = getattr(evento, campo, None)
        if not archivo or archivo.name != nombre:
            if default_storage.exists(nombre):
                default_storage.delete(nombre)


def _decimal_valor(valor):
    """Convierte valores del carrito a Decimal sin propagar errores de formato."""
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def _datos_item_detalle(item):
    """Normaliza un ítem del carrito a precio unitario, cantidad y subtotal.

    El carrito envía ``precio`` como total del ítem y, cuando está disponible,
    ``precio_unitario_original`` como precio unitario. Al editar un evento se
    recalcula el unitario desde el subtotal guardado para no duplicar montos.
    """
    datos = item if isinstance(item, dict) else {}
    cantidad = int(datos.get('cantidad') or 1)
    if cantidad < 1:
        cantidad = 1

    precio_total = _decimal_valor(datos.get('precio'))
    precio_unitario = _decimal_valor(datos.get('precio_unitario_original'))
    if precio_unitario <= 0:
        precio_unitario = precio_total / cantidad

    return {
        'tipo_item': datos.get('tipo', ''),
        'item_id': int(datos.get('id') or 0),
        'nombre_item': datos.get('nombre', ''),
        'cantidad': cantidad,
        'precio_unitario': precio_unitario,
        'subtotal': precio_unitario * cantidad,
    }


def actualizar_estados_eventos():
    """LÃƒÂ³gica para mover eventos a 'En Curso' o 'Finalizado' segÃƒÂºn la hora exacta"""
    ahora = timezone.now()
    
    # Eventos que deben pasar a EN_CURSO
    eventos_programados = Evento.objects.filter(estado='PROGRAMADO')
    for evento in eventos_programados:
        if evento.fecha_inicio and evento.hora_inicio and evento.fecha_fin:
            # Combinar fecha y hora de inicio (hacerlo aware si es necesario)
            inicio_dt = datetime.combine(evento.fecha_inicio, evento.hora_inicio)
            if timezone.is_naive(inicio_dt):
                inicio_dt = timezone.make_aware(inicio_dt)
            
            if inicio_dt <= ahora < evento.fecha_fin:
                evento.estado = 'EN_CURSO'
                evento.save()
    
    # Revertir eventos que estÃƒÂ¡n EN_CURSO pero aÃƒÂºn no han empezado (por error de lÃƒÂ³gica previa)
    eventos_en_curso = Evento.objects.filter(estado='EN_CURSO')
    for evento in eventos_en_curso:
        if evento.fecha_inicio and evento.hora_inicio:
            inicio_dt = datetime.combine(evento.fecha_inicio, evento.hora_inicio)
            if timezone.is_naive(inicio_dt):
                inicio_dt = timezone.make_aware(inicio_dt)
            if ahora < inicio_dt:
                evento.estado = 'PROGRAMADO'
                evento.save()
    
    # Eventos que ya terminaron y estaban EN_CURSO
    Evento.objects.filter(
        fecha_fin__lt=ahora, 
        estado='EN_CURSO'
    ).update(estado='FINALIZADO')

@login_required
def lista_eventos(request):
    from django.core.paginator import Paginator
    from django.db.models import Q
    actualizar_estados_eventos()
    
    q = request.GET.get('q', '').strip()
    order_by = request.GET.get('order_by', '-fecha_inicio')
    
    eventos = Evento.objects.all()
    
    if q:
        eventos = eventos.filter(
            Q(nombre_reserva__icontains=q) | Q(titulo__icontains=q)
        )
        
    # Manejar orden dinÃƒÂ¡mico
    if order_by == 'fecha_asc':
        eventos = eventos.order_by('fecha_inicio', 'hora_inicio')
    elif order_by == 'fecha_desc':
        eventos = eventos.order_by('-fecha_inicio', '-hora_inicio')
    elif order_by == 'hora_asc':
        eventos = eventos.order_by('hora_inicio', 'fecha_inicio')
    elif order_by == 'hora_desc':
        eventos = eventos.order_by('-hora_inicio', '-fecha_inicio')
    elif order_by == 'nombre_asc':
        eventos = eventos.order_by('nombre_reserva')
    elif order_by == 'nombre_desc':
        eventos = eventos.order_by('-nombre_reserva')
    else:
        # Default: MÃƒÂ¡s recientes primero
        eventos = eventos.order_by('-fecha_inicio', '-hora_inicio')

    paginator = Paginator(eventos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'parque/eventos/lista.html', {
        'page_obj': page_obj,
        'q': q,
        'order_by': order_by
    })

@login_required
def crear_evento(request):
    if request.method == 'POST':
        form = EventoForm(request.POST, request.FILES)
        items_json = request.POST.get('items_data')
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    evento = form.save(commit=False)
                    evento.save()
                    
                    total_calculado = 0
                    if items_json:
                        items = json.loads(items_json)
                        for item in items:
                            detalle = DetalleEvento.objects.create(
                                evento=evento, **_datos_item_detalle(item)
                            )
                            total_calculado += detalle.subtotal
                    
                    # Calcular fecha_fin automÃƒÂ¡ticamente
                    if evento.fecha_inicio and evento.hora_inicio:
                        inicio_dt = datetime.combine(evento.fecha_inicio, evento.hora_inicio)
                        evento.fecha_fin = inicio_dt + timedelta(hours=evento.duracion_horas)

                    # Guardamos el total real calculado en el servidor
                    evento.total_pagar = total_calculado
                    evento.save()
                    
                    messages.success(request, f"Evento creado exitosamente. Total: ${total_calculado}")
                    return redirect('parque:detalle_evento', pk=evento.pk)
            except Exception as e:
                messages.error(request, f"Error al guardar: {str(e)}")
    else:
        form = EventoForm()
    
    brazaletes = Brazalete.objects.all()
    productos = ProductoParque.objects.all()
    combos = ComboParque.objects.all()
    
    return render(request, 'parque/eventos/form.html', {
        'form': form, 'titulo': 'Crear Evento',
        'brazaletes': brazaletes, 'productos': productos, 'combos': combos
    })

@login_required
def editar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        nombres_anteriores = _nombres_imagenes(evento)
        form = EventoForm(request.POST, request.FILES, instance=evento)
        items_json = request.POST.get('items_data')
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    evento = form.save(commit=False)
                    evento.detalles.all().delete()
                    
                    total_calculado = 0
                    if items_json:
                        items = json.loads(items_json)
                        for item in items:
                            detalle = DetalleEvento.objects.create(
                                evento=evento, **_datos_item_detalle(item)
                            )
                            total_calculado += detalle.subtotal
                    
                    # Calcular fecha_fin automÃƒÂ¡ticamente
                    if evento.fecha_inicio and evento.hora_inicio:
                        inicio_dt = datetime.combine(evento.fecha_inicio, evento.hora_inicio)
                        evento.fecha_fin = inicio_dt + timedelta(hours=evento.duracion_horas)

                    evento.total_pagar = total_calculado
                    evento.save()
            except Exception as e:
                messages.error(request, f"Error al actualizar: {str(e)}")
            else:
                _limpiar_imagenes_reemplazadas(evento, nombres_anteriores)
                messages.success(request, "Evento actualizado correctamente.")
                return redirect('parque:lista_eventos')
    else:
        form = EventoForm(instance=evento)
    
    detalles_actuales = []
    for d in evento.detalles.all():
        precio_unitario = float(d.subtotal) / d.cantidad if d.cantidad else float(d.precio_unitario)
        detalles_actuales.append({
            'tipo': d.tipo_item, 'id': d.item_id, 'nombre': d.nombre_item,
            'cantidad': d.cantidad, 'precio': float(d.subtotal),
            'precio_unitario_original': precio_unitario,
        })

    return render(request, 'parque/eventos/form.html', {
        'form': form, 'titulo': 'Editar Evento', 'evento': evento,
        'brazaletes': Brazalete.objects.all(),
        'productos': ProductoParque.objects.all(),
        'combos': ComboParque.objects.all(),
        'detalles_actuales': json.dumps(detalles_actuales)
    })

@login_required
def finalizar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    evento.estado = 'FINALIZADO'
    evento.save()
    messages.success(request, f"El evento {evento.titulo} ha sido finalizado con ÃƒÂ©xito.")
    # return redirect('parque:dashboard')
    return redirect('parque:calendario')

# ... Resto de CRUD de productos y combos se mantiene igual ...
@login_required
@eliminar_permitido('parque:lista_eventos')
def eliminar_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        evento.delete()
        messages.success(request, "Evento eliminado correctamente.")
        return redirect('parque:lista_eventos')
    return render(request, 'parque/eventos/eliminar.html', {'evento': evento})

@login_required
def detalle_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    return render(request, 'parque/eventos/detalle.html', {'evento': evento})

@login_required
def generar_pdf_evento(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # TÃƒÂ­tulo
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(190, 10, txt="RECIBO DE RESERVA", ln=True, align='C')
    pdf.ln(10)
    
    # InformaciÃƒÂ³n General
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt=f"Detalles del Evento", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(190, 7, txt=f"Evento: {evento.titulo}", ln=True)
    if evento.nombre_reserva:
        pdf.cell(190, 7, txt=f"Cliente: {evento.nombre_reserva}", ln=True)
    if evento.zona:
        pdf.cell(190, 7, txt=f"Zona: {evento.get_zona_display()}", ln=True)
    pdf.cell(190, 7, txt=f"Estado: {evento.get_estado_display()}", ln=True)
    pdf.cell(190, 7, txt=f"Fecha: {evento.fecha_inicio.strftime('%d/%m/%Y')}", ln=True)
    
    # InformaciÃƒÂ³n de Pagos (Abonos)
    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt=_limpiar_pdf_txt("Información de Pagos / Abonos"), ln=True)
    pdf.set_font("Helvetica", size=10)

    # Abono 1
    if evento.monto_abono1 or evento.metodo_pago:
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(190, 7, txt="Abono 1 (Reserva):", ln=True)
        pdf.set_font("Helvetica", size=10)
        if evento.fecha_abono1:
            pdf.cell(95, 7, txt=f"  Fecha: {evento.fecha_abono1.strftime('%d/%m/%Y')}", ln=False)
        if evento.monto_abono1:
            pdf.cell(95, 7, txt=f"  Monto: ${evento.monto_abono1}", ln=True)
        else:
            pdf.ln(7)
        if evento.tasa_dia:
            pdf.cell(190, 7, txt=f"  Tasa del Dia: {evento.tasa_dia} Bs/$", ln=True)
        if evento.monto_abono1_bs:
            pdf.cell(190, 7, txt=f"  Monto en Bs: Bs {evento.monto_abono1_bs:,.2f}", ln=True)
        if evento.metodo_pago:
            pdf.cell(190, 7, txt=f"  Metodo de Pago: {evento.get_metodo_pago_display()}", ln=True)
        if evento.nota_forma_pago:
            pdf.cell(190, 7, txt=f"  Nota: {evento.nota_forma_pago}", ln=True)
        pdf.ln(2)

    # Abono 2
    if evento.monto_abono2 or evento.metodo_pago2:
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(190, 7, txt=_limpiar_pdf_txt("Abono 2 (Día del Evento):"), ln=True)
        pdf.set_font("Helvetica", size=10)
        if evento.fecha_abono2:
            pdf.cell(95, 7, txt=f"  Fecha: {evento.fecha_abono2.strftime('%d/%m/%Y')}", ln=False)
        if evento.monto_abono2:
            pdf.cell(95, 7, txt=f"  Monto: ${evento.monto_abono2}", ln=True)
        else:
            pdf.ln(7)
        if evento.tasa_dia2:
            pdf.cell(190, 7, txt=f"  Tasa del Dia: {evento.tasa_dia2} Bs/$", ln=True)
        if evento.monto_abono2_bs:
            pdf.cell(190, 7, txt=f"  Monto en Bs: Bs {evento.monto_abono2_bs:,.2f}", ln=True)
        if evento.metodo_pago2:
            pdf.cell(190, 7, txt=f"  Metodo de Pago: {evento.get_metodo_pago2_display()}", ln=True)
        if evento.nota_forma_pago2:
            pdf.cell(190, 7, txt=f"  Nota: {evento.nota_forma_pago2}", ln=True)
        pdf.ln(2)
    
    pdf.ln(5)
    
    # Tabla de Detalles
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt="Items Consumidos:", ln=True)
    pdf.set_font("Helvetica", size=10)
    
    # Cabecera de mini-tabla
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(100, 8, txt="Descripcion", border=1, fill=True)
    pdf.cell(20, 8, txt="Cant.", border=1, fill=True, align='C')
    pdf.cell(35, 8, txt="P. Unit", border=1, fill=True, align='R')
    pdf.cell(35, 8, txt="Subtotal", border=1, fill=True, align='R')
    pdf.ln()
    
    for detalle in evento.detalles.all():
        pdf.cell(100, 8, txt=f"{detalle.nombre_item}", border=1)
        pdf.cell(20, 8, txt=f"{detalle.cantidad}", border=1, align='C')
        pdf.cell(35, 8, txt=f"${detalle.precio_unitario}", border=1, align='R')
        pdf.cell(35, 8, txt=f"${detalle.subtotal}", border=1, align='R')
        pdf.ln()
    
    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(190, 10, txt=f"TOTAL A PAGAR: ${evento.total_pagar}", ln=True, align='R')
    
    # Generar respuesta
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="reserva_{evento.id}.pdf"'
    
    # La salida depende de la version de fpdf, pero esto suele ser lo mas seguro
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        response.write(pdf_output.encode('latin-1', 'replace'))
    elif isinstance(pdf_output, bytearray):
        response.write(bytes(pdf_output))
    else:
        response.write(pdf_output)
        
    return response

@login_required
def generar_pdf_abono1(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # TÃƒÂ­tulo
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(190, 10, txt="RECIBO DE ABONO 1 (RESERVA)", ln=True, align='C')
    pdf.ln(10)
    
    # InformaciÃƒÂ³n General
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt=f"Detalles del Evento", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(190, 7, txt=f"Evento: {evento.titulo}", ln=True)
    if evento.nombre_reserva:
        pdf.cell(190, 7, txt=f"Cliente: {evento.nombre_reserva}", ln=True)
    if evento.zona:
        pdf.cell(190, 7, txt=f"Zona: {evento.get_zona_display()}", ln=True)
    pdf.cell(190, 7, txt=f"Fecha del Evento: {evento.fecha_inicio.strftime('%d/%m/%Y')}", ln=True)
    
    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt=_limpiar_pdf_txt("Información del Abono"), ln=True)
    pdf.set_font("Helvetica", size=11)
    
    if evento.fecha_abono1:
        pdf.cell(190, 7, txt=f"Fecha de Abono: {evento.fecha_abono1.strftime('%d/%m/%Y')}", ln=True)
    if evento.monto_abono1:
        pdf.cell(190, 7, txt=f"Monto: ${evento.monto_abono1}", ln=True)
    if evento.tasa_dia:
        pdf.cell(190, 7, txt=f"Tasa del Dia: {evento.tasa_dia} Bs/$", ln=True)
    if evento.monto_abono1_bs:
        pdf.cell(190, 7, txt=f"Monto en Bs: Bs {evento.monto_abono1_bs:,.2f}", ln=True)
    if evento.metodo_pago:
        pdf.cell(190, 7, txt=f"Metodo de Pago: {evento.get_metodo_pago_display()}", ln=True)
    if evento.nota_forma_pago:
        pdf.cell(190, 7, txt=f"Nota: {evento.nota_forma_pago}", ln=True)
    
    # Generar respuesta
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_abono1_{evento.id}.pdf"'
    
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        response.write(pdf_output.encode('latin-1', 'replace'))
    elif isinstance(pdf_output, bytearray):
        response.write(bytes(pdf_output))
    else:
        response.write(pdf_output)
        
    return response

@login_required
def generar_pdf_abono2(request, pk):
    evento = get_object_or_404(Evento, pk=pk)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    # TÃƒÂ­tulo
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(190, 10, txt=_limpiar_pdf_txt("RECIBO DE ABONO 2 (DÍA DEL EVENTO)"), ln=True, align='C')
    pdf.ln(10)

    # InformaciÃƒÂ³n General
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt="Detalles del Evento", ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(190, 7, txt=f"Evento: {evento.titulo}", ln=True)
    if evento.nombre_reserva:
        pdf.cell(190, 7, txt=f"Cliente: {evento.nombre_reserva}", ln=True)
    if evento.zona:
        pdf.cell(190, 7, txt=f"Zona: {evento.get_zona_display()}", ln=True)
    pdf.cell(190, 7, txt=f"Fecha del Evento: {evento.fecha_inicio.strftime('%d/%m/%Y')}", ln=True)

    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt=_limpiar_pdf_txt("Información del Abono 2"), ln=True)
    pdf.set_font("Helvetica", size=11)

    if evento.fecha_abono2:
        pdf.cell(190, 7, txt=f"Fecha de Abono: {evento.fecha_abono2.strftime('%d/%m/%Y')}", ln=True)
    if evento.monto_abono2:
        pdf.cell(190, 7, txt=f"Monto: ${evento.monto_abono2}", ln=True)
    if evento.tasa_dia2:
        pdf.cell(190, 7, txt=f"Tasa del Dia: {evento.tasa_dia2} Bs/$", ln=True)
    if evento.monto_abono2_bs:
        pdf.cell(190, 7, txt=f"Monto en Bs: Bs {evento.monto_abono2_bs:,.2f}", ln=True)
    if evento.metodo_pago2:
        pdf.cell(190, 7, txt=f"Metodo de Pago: {evento.get_metodo_pago2_display()}", ln=True)
    if evento.nota_forma_pago2:
        pdf.cell(190, 7, txt=f"Nota: {evento.nota_forma_pago2}", ln=True)

    if not evento.monto_abono2 and not evento.metodo_pago2:
        pdf.ln(3)
        pdf.set_font("Helvetica", 'I', 10)
        pdf.cell(190, 7, txt=_limpiar_pdf_txt("Este evento aún no registra un segundo abono."), ln=True)

    # Generar respuesta
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="recibo_abono2_{evento.id}.pdf"'

    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        response.write(pdf_output.encode('latin-1', 'replace'))
    elif isinstance(pdf_output, bytearray):
        response.write(bytes(pdf_output))
    else:
        response.write(pdf_output)

    return response


@login_required
def pagar_abono2(request, pk):
    evento = get_object_or_404(Evento, pk=pk)
    
    total = evento.total_pagar or 0
    abono1 = evento.monto_abono1 or 0
    restante = total - abono1
    if restante < 0:
        restante = 0

    if request.method == 'POST':
        nombres_anteriores = _nombres_imagenes(evento)
        form = Abono2Form(request.POST, request.FILES, instance=evento)
        if form.is_valid():
            form.save()
            _limpiar_imagenes_reemplazadas(evento, nombres_anteriores)
            messages.success(request, f'Abono 2 registrado correctamente para "{evento.titulo}".')
            return redirect('parque:detalle_evento', pk=evento.pk)
    else:
        form = Abono2Form(instance=evento)
        if not evento.monto_abono2:
            form.initial['monto_abono2'] = restante

    return render(request, 'parque/eventos/pagar_abono2.html', {
        'form': form, 
        'evento': evento,
        'restante': restante
    })


@login_required
def actualizar_comprobante_abono1(request, pk):
    """Actualiza solo las fotos del abono 1, sin alterar detalles ni totales."""
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        nombres_anteriores = _nombres_imagenes(evento)
        form = ComprobanteAbono1Form(request.POST, request.FILES, instance=evento)
        if form.is_valid():
            form.save()
            _limpiar_imagenes_reemplazadas(evento, nombres_anteriores)
            messages.success(request, 'Comprobantes del Abono 1 actualizados correctamente.')
            return redirect('parque:detalle_evento', pk=evento.pk)
    else:
        form = ComprobanteAbono1Form(instance=evento)

    return render(request, 'parque/eventos/actualizar_comprobante_abono1.html', {
        'form': form,
        'evento': evento,
    })


@login_required
@eliminar_permitido('parque:calendario')
def borrar_foto_abono1(request, pk):
    """Borra solo la foto del Abono 1 sin afectar ningÃƒÂºn otro dato del evento."""
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        if evento.foto_abono1:
            import os
            if os.path.isfile(evento.foto_abono1.path):
                os.remove(evento.foto_abono1.path)
            # Solo limpia el campo, no toca nada mÃƒÂ¡s
            Evento.objects.filter(pk=pk).update(foto_abono1='')
            messages.success(request, 'Foto del Abono 1 eliminada correctamente.')
        else:
            messages.warning(request, 'Este abono no tiene foto registrada.')
    return redirect('parque:detalle_evento', pk=pk)


@login_required
@eliminar_permitido('parque:calendario')
def borrar_foto_abono2(request, pk):
    """Borra solo la foto del Abono 2 sin afectar ningÃƒÂºn otro dato del evento."""
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        if evento.foto_abono2:
            import os
            if os.path.isfile(evento.foto_abono2.path):
                os.remove(evento.foto_abono2.path)
            Evento.objects.filter(pk=pk).update(foto_abono2='')
            messages.success(request, 'Foto del Abono 2 eliminada correctamente.')
        else:
            messages.warning(request, 'Este abono no tiene foto registrada.')
    return redirect('parque:detalle_evento', pk=pk)

@login_required
@eliminar_permitido('parque:calendario')
def borrar_foto_factura_abono1(request, pk):
    """Borra solo la foto de factura del Abono 1 sin afectar ningun otro dato del evento."""
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        if evento.foto_factura_abono1:
            import os
            if os.path.isfile(evento.foto_factura_abono1.path):
                os.remove(evento.foto_factura_abono1.path)
            Evento.objects.filter(pk=pk).update(foto_factura_abono1='')
            messages.success(request, 'Foto de factura del Abono 1 eliminada correctamente.')
        else:
            messages.warning(request, 'Este abono no tiene foto de factura registrada.')
    return redirect('parque:detalle_evento', pk=pk)


@login_required
@eliminar_permitido('parque:calendario')
def borrar_foto_factura_abono2(request, pk):
    """Borra solo la foto de factura del Abono 2 sin afectar ningun otro dato del evento."""
    evento = get_object_or_404(Evento, pk=pk)
    if request.method == 'POST':
        if evento.foto_factura_abono2:
            import os
            if os.path.isfile(evento.foto_factura_abono2.path):
                os.remove(evento.foto_factura_abono2.path)
            Evento.objects.filter(pk=pk).update(foto_factura_abono2='')
            messages.success(request, 'Foto de factura del Abono 2 eliminada correctamente.')
        else:
            messages.warning(request, 'Este abono no tiene foto de factura registrada.')
    return redirect('parque:detalle_evento', pk=pk)
@login_required
def toggle_confirmado(request, pk, abono_num):
    evento = get_object_or_404(Evento, pk=pk)
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = None
    destino = next_url or None

    if not hasattr(request.user, 'perfilusuario') or request.user.perfilusuario.rol not in ['admin', 'soporte']:
        messages.error(request, "No tienes permisos para confirmar abonos.")
        return redirect(destino) if destino else redirect('parque:detalle_evento', pk=pk)

    nombre_usuario = request.user.get_full_name() or request.user.username

    if request.method == 'POST':
        if abono_num == 1:
            if evento.confirmado == 'Sí':
                evento.confirmado = ''
                evento.confirmado_usuario = ''
            else:
                evento.confirmado = 'Sí'
                evento.confirmado_usuario = nombre_usuario
        elif abono_num == 2:
            if evento.confirmado2 == 'Sí':
                evento.confirmado2 = ''
                evento.confirmado_usuario2 = ''
            else:
                evento.confirmado2 = 'Sí'
                evento.confirmado_usuario2 = nombre_usuario
        evento.save()
        messages.success(request, f"Estado de confirmación de Abono {abono_num} actualizado.")

    return redirect(destino) if destino else redirect('parque:detalle_evento', pk=pk)


@login_required
def toggle_vista_banco(request, pk, abono_num):
    """Alterna el botón Sí/No de «Vista Banco» de un abono (solo admin/soporte)."""
    evento = get_object_or_404(Evento, pk=pk)
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = None
    destino = next_url or None

    rol = getattr(getattr(request.user, 'perfilusuario', None), 'rol', '')
    if rol not in ('admin', 'soporte'):
        messages.error(request, "No tienes permisos para modificar la vista banco.")
        return redirect(destino) if destino else redirect('parque:detalle_evento', pk=pk)

    if request.method == 'POST':
        if abono_num == 1:
            evento.vista_banco = not evento.vista_banco if evento.vista_banco is not None else True
        elif abono_num == 2:
            evento.vista_banco2 = not evento.vista_banco2 if evento.vista_banco2 is not None else True
        evento.save(update_fields=['vista_banco', 'vista_banco2'])
        messages.success(request, f"Vista Banco del Abono {abono_num} actualizada.")

    return redirect(destino) if destino else redirect('parque:detalle_evento', pk=pk)


@login_required
def lista_productos(request):
    from django.core.paginator import Paginator
    productos = ProductoParque.objects.all().order_by('nombre')
    paginator = Paginator(productos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'parque/productos/lista.html', {'page_obj': page_obj})

@login_required
def crear_producto(request):
    if request.method == 'POST':
        form = ProductoParqueForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto registrado correctamente.")
            return redirect('parque:lista_productos')
    else:
        form = ProductoParqueForm()
    return render(request, 'parque/productos/form.html', {'form': form, 'titulo': 'Registrar Producto'})

@login_required
def editar_producto(request, pk):
    producto = get_object_or_404(ProductoParque, pk=pk)
    if request.method == 'POST':
        form = ProductoParqueForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, "Producto actualizado correctamente.")
            return redirect('parque:lista_productos')
    else:
        form = ProductoParqueForm(instance=producto)
    return render(request, 'parque/productos/form.html', {'form': form, 'titulo': 'Editar Producto'})

@login_required
@eliminar_permitido('parque:lista_productos')
def eliminar_producto(request, pk):
    producto = get_object_or_404(ProductoParque, pk=pk)
    if request.method == 'POST':
        producto.delete()
        messages.success(request, "Producto eliminado.")
        return redirect('parque:lista_productos')
    return render(request, 'parque/productos/eliminar.html', {'producto': producto})

@login_required
def lista_combos(request):
    combos = ComboParque.objects.all().order_by('nombre')
    return render(request, 'parque/combos/lista.html', {'combos': combos})

@login_required
def crear_combo(request):
    if request.method == 'POST':
        form = ComboParqueForm(request.POST)
        items_json = request.POST.get('items_data')
        if form.is_valid():
            try:
                with transaction.atomic():
                    combo = form.save()
                    if items_json:
                        items = json.loads(items_json)
                        for item in items:
                            ProductoEnCombo.objects.create(
                                combo=combo,
                                producto_id=item['id'],
                                cantidad=item['cantidad']
                            )
                    messages.success(request, "Combo creado correctamente.")
                    return redirect('parque:lista_combos')
            except Exception as e:
                messages.error(request, f"Error al guardar el combo: {str(e)}")
    else:
        form = ComboParqueForm()
    
    productos = ProductoParque.objects.all()
    return render(request, 'parque/combos/form.html', {
        'form': form, 'titulo': 'Crear Nuevo Combo',
        'productos': productos
    })

@login_required
def editar_combo(request, pk):
    combo = get_object_or_404(ComboParque, pk=pk)
    if request.method == 'POST':
        form = ComboParqueForm(request.POST, instance=combo)
        items_json = request.POST.get('items_data')
        if form.is_valid():
            try:
                with transaction.atomic():
                    combo = form.save()
                    combo.items.all().delete()
                    if items_json:
                        items = json.loads(items_json)
                        for item in items:
                            ProductoEnCombo.objects.create(
                                combo=combo,
                                producto_id=item['id'],
                                cantidad=item['cantidad']
                            )
                    messages.success(request, "Combo actualizado correctamente.")
                    return redirect('parque:lista_combos')
            except Exception as e:
                messages.error(request, f"Error al actualizar: {str(e)}")
    else:
        form = ComboParqueForm(instance=combo)
    
    productos = ProductoParque.objects.all()
    
    detalles_actuales = []
    for item in combo.items.all():
        detalles_actuales.append({
            'id': item.producto.id,
            'nombre': item.producto.nombre,
            'cantidad': item.cantidad
        })

    return render(request, 'parque/combos/form.html', {
        'form': form, 'titulo': 'Editar Combo',
        'productos': productos,
        'detalles_actuales': json.dumps(detalles_actuales)
    })

@login_required
@eliminar_permitido('parque:lista_combos')
def eliminar_combo(request, pk):
    combo = get_object_or_404(ComboParque, pk=pk)
    if request.method == 'POST':
        combo.delete()
        messages.success(request, "Combo eliminado correctamente.")
        return redirect('parque:lista_combos')
    return render(request, 'parque/combos/eliminar.html', {'combo': combo})

@login_required
def lista_brazaletes(request):
    brazaletes = Brazalete.objects.all().order_by('cantidad')
    return render(request, 'parque/brazaletes/lista.html', {'brazaletes': brazaletes})

@login_required
def crear_brazalete(request):
    if request.method == 'POST':
        form = BrazaleteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "ConfiguraciÃƒÂ³n de brazalete guardada.")
            return redirect('parque:lista_brazaletes')
    else:
        form = BrazaleteForm()
    return render(request, 'parque/brazaletes/form.html', {'form': form, 'titulo': 'Configurar Nuevo Brazalete/Combo'})

@login_required
def editar_brazalete(request, pk):
    brazalete = get_object_or_404(Brazalete, pk=pk)
    if request.method == 'POST':
        form = BrazaleteForm(request.POST, instance=brazalete)
        if form.is_valid():
            form.save()
            messages.success(request, "ConfiguraciÃƒÂ³n actualizada.")
            return redirect('parque:lista_brazaletes')
    else:
        form = BrazaleteForm(instance=brazalete)
    return render(request, 'parque/brazaletes/form.html', {'form': form, 'titulo': 'Editar ConfiguraciÃƒÂ³n'})

@login_required
@eliminar_permitido('parque:lista_brazaletes')
def eliminar_brazalete(request, pk):
    brazalete = get_object_or_404(Brazalete, pk=pk)
    if request.method == 'POST':
        brazalete.delete()
        messages.success(request, "ConfiguraciÃƒÂ³n eliminada.")
        return redirect('parque:lista_brazaletes')
    return render(request, 'parque/brazaletes/eliminar.html', {'brazalete': brazalete})


def _obtener_abonos_filtrados(request):
    """Extrae y filtra los abonos 1 y 2 según los parámetros de la solicitud."""
    from django.db.models import Q
    from datetime import date
    actualizar_estados_eventos()

    q = request.GET.get('q', '').strip()
    filtro_tipo = request.GET.get('tipo', '').strip()  # '1', '2' o ''
    filtro_confirmado = request.GET.get('confirmado', '').strip()  # 'si', 'no' o ''
    desde = request.GET.get('desde', '').strip()
    hasta = request.GET.get('hasta', '').strip()

    # Traer todos los eventos que tengan al menos un abono registrado
    eventos = Evento.objects.filter(
        Q(monto_abono1__gt=0) | Q(fecha_abono1__isnull=False) |
        Q(monto_abono2__gt=0) | Q(fecha_abono2__isnull=False)
    ).order_by('-fecha_inicio', '-hora_inicio')

    if q:
        eventos = eventos.filter(
            Q(nombre_reserva__icontains=q) |
            Q(titulo__icontains=q) |
            Q(referencia_bancaria__icontains=q) |
            Q(referencia_bancaria2__icontains=q) |
            Q(banco__icontains=q) |
            Q(banco2__icontains=q)
        )

    abonos = []
    total_monto = 0.0
    total_monto_bs = 0.0

    for ev in eventos:
        # Abono 1
        tiene_abono1 = bool(ev.monto_abono1) or bool(ev.fecha_abono1) or bool(ev.metodo_pago)
        if tiene_abono1:
            fecha_a1 = ev.fecha_abono1
            if not desde or (fecha_a1 and fecha_a1.strftime('%Y-%m-%d') >= desde):
                if not hasta or (fecha_a1 and fecha_a1.strftime('%Y-%m-%d') <= hasta):
                    es_conf1 = (ev.confirmado == 'Sí')
                    pasa_conf1 = True
                    if filtro_confirmado == 'si' and not es_conf1:
                        pasa_conf1 = False
                    elif filtro_confirmado == 'no' and es_conf1:
                        pasa_conf1 = False

                    if pasa_conf1 and (not filtro_tipo or filtro_tipo == '1'):
                        abonos.append({
                            'evento': ev,
                            'tipo_numero': 1,
                            'tipo_label': 'Abono 1 (Reserva)',
                            'tipo_corto': 'Abono 1',
                            'fecha': fecha_a1,
                            'monto': float(ev.monto_abono1 or 0),
                            'metodo': ev.get_metodo_pago_display() if ev.metodo_pago else 'No especificado',
                            'nota': ev.nota_forma_pago or '-',
                            'confirmado_por': ev.confirmado_por or '-',
                            'tasa': ev.tasa_dia or '-',
                            'monto_bs': ev.monto_abono1_bs,
                            'banco': ev.banco or '-',
                            'ref': ev.referencia_bancaria or '-',
                            'confirmado': ev.confirmado,
                            'confirmado_usuario': ev.confirmado_usuario or '',
                            'vista_banco': ev.vista_banco,
                            'foto': ev.foto_abono1,
                            'foto_factura': ev.foto_factura_abono1,
                        })
                        total_monto += float(ev.monto_abono1 or 0)
                        total_monto_bs += float(ev.monto_abono1_bs or 0)

        # Abono 2
        tiene_abono2 = bool(ev.monto_abono2) or bool(ev.fecha_abono2) or bool(ev.metodo_pago2)
        if tiene_abono2:
            fecha_a2 = ev.fecha_abono2
            if not desde or (fecha_a2 and fecha_a2.strftime('%Y-%m-%d') >= desde):
                if not hasta or (fecha_a2 and fecha_a2.strftime('%Y-%m-%d') <= hasta):
                    es_conf2 = (ev.confirmado2 == 'Sí')
                    pasa_conf2 = True
                    if filtro_confirmado == 'si' and not es_conf2:
                        pasa_conf2 = False
                    elif filtro_confirmado == 'no' and es_conf2:
                        pasa_conf2 = False

                    if pasa_conf2 and (not filtro_tipo or filtro_tipo == '2'):
                        abonos.append({
                            'evento': ev,
                            'tipo_numero': 2,
                            'tipo_label': 'Abono 2 (Día del Evento)',
                            'tipo_corto': 'Abono 2',
                            'fecha': fecha_a2,
                            'monto': float(ev.monto_abono2 or 0),
                            'metodo': ev.get_metodo_pago2_display() if ev.metodo_pago2 else 'No especificado',
                            'nota': ev.nota_forma_pago2 or '-',
                            'confirmado_por': ev.confirmado_por2 or '-',
                            'tasa': ev.tasa_dia2 or '-',
                            'monto_bs': ev.monto_abono2_bs,
                            'banco': ev.banco2 or '-',
                            'ref': ev.referencia_bancaria2 or '-',
                            'confirmado': ev.confirmado2,
                            'confirmado_usuario': ev.confirmado_usuario2 or '',
                            'vista_banco': ev.vista_banco2,
                            'foto': ev.foto_abono2,
                            'foto_factura': ev.foto_factura_abono2,
                        })
                        total_monto += float(ev.monto_abono2 or 0)
                        total_monto_bs += float(ev.monto_abono2_bs or 0)

    # Ordenar por fecha de abono desc (los más recientes primero)
    abonos.sort(key=lambda a: (a['fecha'] or a['evento'].fecha_inicio or date.min), reverse=True)

    return {
        'abonos': abonos,
        'total_monto': round(total_monto, 2),
        'total_monto_bs': round(total_monto_bs, 2),
        'total_registros': len(abonos),
        'q': q,
        'filtro_tipo': filtro_tipo,
        'filtro_confirmado': filtro_confirmado,
        'desde': desde,
        'hasta': hasta,
    }


def _limpiar_pdf_txt(texto):
    """Sanitiza strings para evitar excepciones de codificación con FPDF estándar."""
    if not texto:
        return ''
    texto = str(texto)
    reemplazos = {
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Ñ': 'N', 'ñ': 'n', '–': '-', '—': '-', '“': '"', '”': '"',
        '‘': "'", '’': "'", '°': 'o', 'º': 'o', 'ª': 'a', '€': 'EUR',
    }
    for orig, rep in reemplazos.items():
        texto = texto.replace(orig, rep)
    return texto.encode('latin-1', 'replace').decode('latin-1')


@login_required
def lista_abonos(request):
    """Listado completo y detallado de todos los abonos realizados en los eventos del parque con paginación de 10."""
    if not (hasattr(request.user, 'perfilusuario') and request.user.perfilusuario.rol.lower() in ['soporte', 'parque', 'admin']):
        messages.error(request, "No tienes permisos para acceder a esta sección.")
        return redirect('index')

    from django.core.paginator import Paginator

    datos = _obtener_abonos_filtrados(request)
    abonos = datos['abonos']

    # Paginación hasta 10 registros por página
    paginator = Paginator(abonos, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Preservar filtros actuales en los links de paginación
    params = request.GET.copy()
    if 'page' in params:
        del params['page']
    querystring = params.urlencode()

    context = {
        **datos,
        'page_obj': page_obj,
        'querystring': querystring,
    }
    return render(request, 'parque/eventos/abonos.html', context)


@login_required
def generar_pdf_abonos(request):
    """Genera un reporte PDF desglosado en formato lista/tabla de los abonos del parque."""
    if not (hasattr(request.user, 'perfilusuario') and request.user.perfilusuario.rol.lower() in ['soporte', 'parque', 'admin']):
        messages.error(request, "No tienes permisos para acceder a esta función.")
        return redirect('index')

    datos = _obtener_abonos_filtrados(request)
    abonos = datos['abonos']
    total_monto = datos['total_monto']
    total_monto_bs = datos['total_monto_bs']
    total_registros = datos['total_registros']

    # Hoja Horizontal (Landscape) para presentar todas las columnas cómodamente
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # Título Principal
    pdf.set_font("Helvetica", 'B', 15)
    pdf.cell(0, 8, txt=_limpiar_pdf_txt("CONTROL PARQUE - REPORTE DETALLADO DE ABONOS Y PAGOS"), ln=True, align='C')

    # Subtítulo con filtros y fecha de generación
    from django.utils import timezone
    ahora = timezone.localtime(timezone.now()).strftime("%d/%m/%Y %H:%M")
    filtros_txt = []
    if datos['desde']:
        filtros_txt.append(f"Desde: {datos['desde']}")
    if datos['hasta']:
        filtros_txt.append(f"Hasta: {datos['hasta']}")
    if datos['filtro_tipo']:
        filtros_txt.append(f"Tipo: Abono {datos['filtro_tipo']}")
    if datos['filtro_confirmado']:
        filtros_txt.append(f"Confirmado: {'Si' if datos['filtro_confirmado'] == 'si' else 'No'}")
    if datos['q']:
        filtros_txt.append(f"Busqueda: '{datos['q']}'")

    subtitulo = f"Generado: {ahora}"
    if filtros_txt:
        subtitulo += " | Filtros: " + ", ".join(filtros_txt)
    else:
        subtitulo += " | Mostrando todos los registros"

    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 5, txt=_limpiar_pdf_txt(subtitulo), ln=True, align='C')
    pdf.ln(3)

    # Bloque de Resumen
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_fill_color(230, 245, 235)
    resumen_txt = f"TOTAL ABONOS REGISTRADOS: {total_registros}    |    MONTO TOTAL RECAUDADO: ${total_monto:,.2f}    |    EQUIVALENTE: Bs {total_monto_bs:,.2f}"
    pdf.cell(0, 7, txt=_limpiar_pdf_txt(resumen_txt), border=1, ln=True, align='C', fill=True)
    pdf.ln(3)

    # Columnas de la tabla (Ancho total disponible ~273mm en A4 Landscape con márgenes)
    # Fecha: 22mm
    # Cliente / Evento: 42mm
    # Tipo: 24mm
    # Monto: 22mm
    # Metodo: 26mm
    # Banco: 24mm
    # Referencia: 26mm
    # Tasa: 16mm
    # Monto Bs: 22mm
    # Conf.: 16mm
    # Confirmado Por: 33mm
    # Suma: 22+42+24+22+26+24+26+16+22+16+33 = 273mm
    cols = [
        ("Fecha", 22, 'C'),
        ("Cliente / Evento", 42, 'L'),
        ("Tipo Abono", 24, 'C'),
        ("Monto ($)", 22, 'R'),
        ("Metodo", 26, 'L'),
        ("Banco", 24, 'L'),
        ("Referencia", 26, 'L'),
        ("Tasa", 16, 'C'),
        ("Monto (Bs)", 22, 'R'),
        ("Conf.", 16, 'C'),
        ("Confirmado Por", 33, 'L'),
    ]

    # Encabezado de la tabla
    pdf.set_font("Helvetica", 'B', 8)
    pdf.set_fill_color(40, 116, 166)
    pdf.set_text_color(255, 255, 255)
    for titulo_col, ancho, alineacion in cols:
        pdf.cell(ancho, 7, txt=_limpiar_pdf_txt(titulo_col), border=1, fill=True, align=alineacion)
    pdf.ln()

    # Filas de la lista
    pdf.set_font("Helvetica", size=7.5)
    pdf.set_text_color(0, 0, 0)
    fill = False

    for a in abonos:
        ev = a['evento']
        fecha_str = a['fecha'].strftime('%d/%m/%Y') if a['fecha'] else '-'
        cliente_ev = f"{ev.nombre_reserva or ev.titulo or 'Evento #' + str(ev.id)}"
        if len(cliente_ev) > 28:
            cliente_ev = cliente_ev[:26] + '..'
        tipo_str = a['tipo_corto']
        monto_str = f"${float(a['monto']):,.2f}"
        metodo_str = (a['metodo'] or '-')[:16]
        banco_str = (a['banco'] or '-')[:15]
        ref_str = (a['ref'] or '-')[:16]
        tasa_str = str(a['tasa'] or '-')[:10]
        monto_bs = a.get('monto_bs')
        monto_bs_str = f"Bs {float(monto_bs):,.2f}" if monto_bs else '-'
        conf_str = "SI" if a['confirmado'] == 'Sí' else "NO"
        conf_por = (a['confirmado_usuario'] or a['confirmado_por'] or '-')[:25]

        if fill:
            pdf.set_fill_color(245, 247, 250)
        else:
            pdf.set_fill_color(255, 255, 255)

        pdf.cell(22, 6, txt=_limpiar_pdf_txt(fecha_str), border='TB', fill=fill, align='C')
        pdf.cell(42, 6, txt=_limpiar_pdf_txt(cliente_ev), border='TB', fill=fill, align='L')
        pdf.cell(24, 6, txt=_limpiar_pdf_txt(tipo_str), border='TB', fill=fill, align='C')
        pdf.cell(22, 6, txt=_limpiar_pdf_txt(monto_str), border='TB', fill=fill, align='R')
        pdf.cell(26, 6, txt=_limpiar_pdf_txt(metodo_str), border='TB', fill=fill, align='L')
        pdf.cell(24, 6, txt=_limpiar_pdf_txt(banco_str), border='TB', fill=fill, align='L')
        pdf.cell(26, 6, txt=_limpiar_pdf_txt(ref_str), border='TB', fill=fill, align='L')
        pdf.cell(16, 6, txt=_limpiar_pdf_txt(tasa_str), border='TB', fill=fill, align='C')
        pdf.cell(22, 6, txt=_limpiar_pdf_txt(monto_bs_str), border='TB', fill=fill, align='R')
        pdf.cell(16, 6, txt=_limpiar_pdf_txt(conf_str), border='TB', fill=fill, align='C')
        pdf.cell(33, 6, txt=_limpiar_pdf_txt(conf_por), border='TB', fill=fill, align='L')
        pdf.ln()
        fill = not fill

    # Fila totalizadora al final
    pdf.set_font("Helvetica", 'B', 8)
    pdf.set_fill_color(230, 235, 240)
    pdf.cell(22 + 42 + 24, 7, txt=_limpiar_pdf_txt(f"TOTAL GENERAL ({total_registros} abonos)"), border=1, fill=True, align='R')
    pdf.cell(22, 7, txt=_limpiar_pdf_txt(f"${total_monto:,.2f}"), border=1, fill=True, align='R')
    pdf.cell(26 + 24 + 26 + 16, 7, txt="", border=1, fill=True)
    pdf.cell(22, 7, txt=_limpiar_pdf_txt(f"Bs {total_monto_bs:,.2f}"), border=1, fill=True, align='R')
    pdf.cell(16 + 33, 7, txt="", border=1, fill=True)
    pdf.ln()

    # Retorno en modo inline para vista previa e impresión directa en el navegador
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="reporte_abonos_parque.pdf"'
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        response.write(pdf_output.encode('latin-1', 'replace'))
    elif isinstance(pdf_output, bytearray):
        response.write(bytes(pdf_output))
    else:
        response.write(pdf_output)
    return response



