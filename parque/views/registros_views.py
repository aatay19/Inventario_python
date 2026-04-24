import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from ..models import Evento, ProductoParque, ComboParque, Brazalete, DetalleEvento, ProductoEnCombo
from ..forms import EventoForm, ProductoParqueForm, ComboParqueForm, BrazaleteForm

def actualizar_estados_eventos():
    """Lógica para mover eventos a 'En Curso' o 'Finalizado' según la hora"""
    ahora = timezone.now()
    # Eventos que deben pasar a EN_CURSO
    Evento.objects.filter(
        fecha_inicio__lte=ahora, 
        fecha_fin__gte=ahora, 
        estado='PROGRAMADO'
    ).update(estado='EN_CURSO')
    
    # Eventos que ya terminaron y estaban EN_CURSO
    Evento.objects.filter(
        fecha_fin__lt=ahora, 
        estado='EN_CURSO'
    ).update(estado='FINALIZADO')

@login_required
def lista_eventos(request):
    actualizar_estados_eventos()
    eventos = Evento.objects.all().order_by('-fecha_inicio')
    return render(request, 'parque/eventos/lista.html', {'eventos': eventos})

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
                                precio_unitario=item['precio']
                            )
                            total_calculado += detalle.subtotal
                    
                    # Guardamos el total real calculado en el servidor
                    evento.total_pagar = total_calculado
                    evento.save()
                    
                    messages.success(request, f"Evento creado exitosamente. Total: ${total_calculado}")
                    return redirect('parque:lista_eventos')
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
                                precio_unitario=item['precio']
                            )
                            total_calculado += detalle.subtotal
                    
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
def lista_productos(request):
    productos = ProductoParque.objects.all().order_by('nombre')
    return render(request, 'parque/productos/lista.html', {'productos': productos})

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
    precios_productos = {p.id: float(p.precio) for p in productos}
    return render(request, 'parque/combos/form.html', {
        'form': form, 'titulo': 'Crear Nuevo Combo',
        'productos': productos,
        'precios_productos': json.dumps(precios_productos)
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
    precios_productos = {p.id: float(p.precio) for p in productos}
    
    detalles_actuales = []
    for item in combo.items.all():
        detalles_actuales.append({
            'id': item.producto.id,
            'nombre': item.producto.nombre,
            'cantidad': item.cantidad,
            'precio': float(item.producto.precio)
        })

    return render(request, 'parque/combos/form.html', {
        'form': form, 'titulo': 'Editar Combo',
        'productos': productos,
        'precios_productos': json.dumps(precios_productos),
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
