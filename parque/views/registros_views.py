import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from fpdf import FPDF
from ..models import Evento, ProductoParque, ComboParque, Brazalete, DetalleEvento, ProductoEnCombo
from ..forms import EventoForm, ProductoParqueForm, ComboParqueForm, BrazaleteForm

def actualizar_estados_eventos():
    """Lógica para mover eventos a 'En Curso' o 'Finalizado' según la hora exacta"""
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
    
    # Revertir eventos que están EN_CURSO pero aún no han empezado (por error de lógica previa)
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
        
    # Manejar orden dinámico
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
        # Default: Más recientes primero
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
        form = EventoForm(request.POST)
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
                                evento=evento,
                                tipo_item=item['tipo'],
                                item_id=item['id'],
                                nombre_item=item['nombre'],
                                cantidad=item['cantidad'],
                                precio_unitario=item['precio'],
                                subtotal=item['precio']
                            )
                            total_calculado += detalle.subtotal
                    
                    # Calcular fecha_fin automáticamente
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
        form = EventoForm(request.POST, instance=evento)
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
                                evento=evento,
                                tipo_item=item['tipo'],
                                item_id=item['id'],
                                nombre_item=item['nombre'],
                                cantidad=item['cantidad'],
                                precio_unitario=item['precio'],
                                subtotal=item['precio']
                            )
                            total_calculado += detalle.subtotal
                    
                    # Calcular fecha_fin automáticamente
                    if evento.fecha_inicio and evento.hora_inicio:
                        inicio_dt = datetime.combine(evento.fecha_inicio, evento.hora_inicio)
                        evento.fecha_fin = inicio_dt + timedelta(hours=evento.duracion_horas)

                    evento.total_pagar = total_calculado
                    evento.save()
                    
                    messages.success(request, "Evento actualizado correctamente.")
                    return redirect('parque:lista_eventos')
            except Exception as e:
                messages.error(request, f"Error al actualizar: {str(e)}")
    else:
        form = EventoForm(instance=evento)
    
    detalles_actuales = []
    for d in evento.detalles.all():
        detalles_actuales.append({
            'tipo': d.tipo_item, 'id': d.item_id, 'nombre': d.nombre_item,
            'cantidad': d.cantidad, 'precio': float(d.precio_unitario)
        })

    return render(request, 'parque/eventos/form.html', {
        'form': form, 'titulo': 'Editar Evento',
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
    messages.success(request, f"El evento {evento.titulo} ha sido finalizado con éxito.")
    return redirect('parque:dashboard')

# ... Resto de CRUD de productos y combos se mantiene igual ...
@login_required
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
    
    # Título
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(190, 10, txt="RECIBO DE RESERVA", ln=True, align='C')
    pdf.ln(10)
    
    # Información General
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
    
    # Información de Pagos (Abonos)
    pdf.ln(5)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(190, 8, txt="Información de Pagos / Abonos", ln=True)
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
        if evento.metodo_pago:
            pdf.cell(190, 7, txt=f"  Metodo de Pago: {evento.get_metodo_pago_display()}", ln=True)
        if evento.nota_forma_pago:
            pdf.cell(190, 7, txt=f"  Nota: {evento.nota_forma_pago}", ln=True)
        pdf.ln(2)

    # Abono 2
    if evento.monto_abono2 or evento.metodo_pago2:
        pdf.set_font("Helvetica", 'B', 10)
        pdf.cell(190, 7, txt="Abono 2 (Día del Evento):", ln=True)
        pdf.set_font("Helvetica", size=10)
        if evento.fecha_abono2:
            pdf.cell(95, 7, txt=f"  Fecha: {evento.fecha_abono2.strftime('%d/%m/%Y')}", ln=False)
        if evento.monto_abono2:
            pdf.cell(95, 7, txt=f"  Monto: ${evento.monto_abono2}", ln=True)
        else:
            pdf.ln(7)
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
        response.write(pdf_output.encode('latin-1'))
    else:
        response.write(pdf_output)
        
    return response

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
            messages.success(request, "Configuración de brazalete guardada.")
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
            messages.success(request, "Configuración actualizada.")
            return redirect('parque:lista_brazaletes')
    else:
        form = BrazaleteForm(instance=brazalete)
    return render(request, 'parque/brazaletes/form.html', {'form': form, 'titulo': 'Editar Configuración'})

@login_required
def eliminar_brazalete(request, pk):
    brazalete = get_object_or_404(Brazalete, pk=pk)
    if request.method == 'POST':
        brazalete.delete()
        messages.success(request, "Configuración eliminada.")
        return redirect('parque:lista_brazaletes')
    return render(request, 'parque/brazaletes/eliminar.html', {'brazalete': brazalete})
