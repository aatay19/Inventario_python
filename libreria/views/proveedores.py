import openpyxl
import csv
import io
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.contrib import messages
from django.core.paginator import Paginator
from .auth import es_pleno_acceso
from ..models import Proveedor
from ..forms import ProveedorForm, ImportarArchivoForm

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def proveedores_index(request):
    q = request.GET.get('q', '').strip()
    order = request.GET.get('order', 'razonsocial_asc')
    page_size = 10
    qs = Proveedor.objects.all()

    if q:
        qs = qs.filter(
            Q(nombre__icontains=q) |
            Q(rif__icontains=q) |
            Q(razonsocial__icontains=q)
        )

    if order == 'razonsocial_desc':
        qs = qs.order_by('-razonsocial')
    else:
        qs = qs.order_by('razonsocial')

    paginator = Paginator(qs, page_size)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'proveedores/index.html', {
        'page_obj': page_obj,
        'q': q,
        'order': order,
    })

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def proveedores_crear(request):
    formulario_proveedores = ProveedorForm(request.POST or None)
    if formulario_proveedores.is_valid():
        formulario_proveedores.save()
        messages.success(request, 'Proveedor registrado exitosamente.')
        return redirect('/proveedores')
    return render(request, 'proveedores/crear.html', {'formulario_proveedores': formulario_proveedores})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def proveedores_editar(request, id):
    proveedor = Proveedor.objects.get(id=id)
    formulario_proveedores = ProveedorForm(request.POST or None, instance=proveedor)
    if formulario_proveedores.is_valid() and request.POST:
        formulario_proveedores.save()
        messages.success(request, 'Proveedor actualizado exitosamente.')
        return redirect('/proveedores')
    return render(request, 'proveedores/editar.html',{'formulario_proveedores': formulario_proveedores})

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def proveedores_eliminar(request, id):
    proveedores = Proveedor.objects.get(id=id)
    proveedores.delete()
    messages.success(request, 'Proveedor eliminado exitosamente.')
    return redirect('/proveedores')

@login_required
@user_passes_test(es_pleno_acceso, login_url='index')
def proveedores_importar(request):
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
                        if row and row[0]:
                            datos.append(row)
                
                for i, fila in enumerate(datos):
                    try:
                        Proveedor.objects.create(
                            nombre=fila[0],
                            telefono=fila[1] if len(fila) > 1 else '',
                            razonsocial=fila[2] if len(fila) > 2 else '',
                            rif=fila[3] if len(fila) > 3 else f"S/R-{i}",
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
