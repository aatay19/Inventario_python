from django import forms
from django.contrib.auth.models import User
from .models import Cliente, Proveedor, Inventario, HistorialProveedoresNotas, MovimientosInventario, PerfilUsuario
from django.db import transaction
import re
from django.forms import ModelChoiceField

class ProductoModelChoiceField(ModelChoiceField):
    """
    Campo de selección de productos que muestra más detalles.
    """
    def label_from_instance(self, obj):
        # Formato: "Nombre (Stock: 10) - Precio: Bs 123.45"
        codigo = f"[{obj.codigo_producto}] " if obj.codigo_producto else ""
        return f"{codigo}{obj.nombre_producto} (Stock: {obj.cantidad}) - Costo: Bs {obj.costo_actual:,.2f}"

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = '__all__'

class ProveedorForm(forms.ModelForm):
    class Meta:
        model = Proveedor
        fields = '__all__'    

class InventarioForm(forms.ModelForm):
    total_empaques = forms.CharField(
        required=False, 
        label="Total de Empaques",
        widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': 'readonly'})
    )

    class Meta:    
        model = Inventario
        fields = '__all__'
        # Orden solicitado:
        # 1. CÓDIGO, 2. LECTURA (UI), 3. NOMBRE, 4. DESCRIPCIÓN, 5. CATEGORIA, 
        # 6. CANTIDAD UNITARIA, 7. UNIDAD DEL EMPAQUE, 8. CANTIDAD POR EMPAQUE, 
        # 9. TOTAL DE EMPAQUES, 10. COSTO ACTUAL, 11. COSTO ANTERIOR
        field_order = [
            'codigo_producto', 'nombre_producto', 'descripcion', 'categoria', 
            'cantidad', 'unidad_empaque', 'cantidad_por_empaque', 'total_empaques', 
            'costo_actual', 'costo_anterior', 'stock_minimo', 'stock_maximo'
        ]
        widgets = {
            'codigo_producto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Código interno (p. ej. ABC-123 o SKU 001)',
                'maxlength': '50',
            }),
            'nombre_producto': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'unidad_empaque': forms.Select(attrs={'class': 'form-control'}),
            'cantidad_por_empaque': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'costo_actual': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'costo_anterior': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_minimo': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'stock_maximo': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Calcular total_empaques si hay instancia
        if self.instance and self.instance.pk:
            self.fields['total_empaques'].initial = self.instance.total_empaques
        
        # Reordenar campos explícitamente para asegurar el orden en el template
        if self.Meta.field_order:
            self.fields = {k: self.fields[k] for k in self.Meta.field_order if k in self.fields}


    def clean_codigo_producto(self):
        codigo = self.cleaned_data.get('codigo_producto')
        if codigo:
            codigo = codigo.strip()
            # permitir letras, números, espacios y guiones
            if not re.match(r'^[A-Za-z0-9\s\-]+$', codigo):
                raise forms.ValidationError("El código sólo puede contener letras, números, espacios y guiones (-).")
            # normalizar a mayúsculas para consistencia (opcional)
            codigo = codigo.upper()
            # comprobar unicidad ignorando el propio registro al editar
            qs = Inventario.objects.filter(codigo_producto__iexact=codigo)
            if self.instance and getattr(self.instance, "pk", None):
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError("Este código ya está en uso por otro producto.")
        return codigo



# Form para uso independiente (p. ej. crear nota desde una vista fuera del inline)
class HistorialProveedoresNotasForm(forms.ModelForm):
    # campo de solo lectura para mostrar la fecha (no está ligado al modelo)
    fecha_registro_display = forms.DateTimeField(required=False, disabled=True, label='Fecha de Registro')
    
    producto = ProductoModelChoiceField(
        queryset=Inventario.objects.order_by('nombre_producto'),
        widget=forms.Select(attrs={'class': 'form-select select2'}),
        required=False,
        label="Producto (Opcional)"
    )

    unidades_por_empaque = forms.IntegerField(
        required=False,
        label="Unidades por Empaque",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Ej. 12'})
    )

    class Meta:
        model = HistorialProveedoresNotas
        # no incluir 'fecha_registro' porque es auto_now_add (no editable)
        fields = ('proveedores', 'producto', 'unidad_empaque', 'cantidad_empaques', 'total_unidades', 'detalle_nota',)

        widgets = {
            'proveedores': forms.Select(attrs={'class': 'form-select select2'}),
            'unidad_empaque': forms.Select(attrs={'class': 'form-select'}),
            'cantidad_empaques': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
            'total_unidades': forms.NumberInput(attrs={'class': 'form-control', 'readonly': 'readonly'}),
            'detalle_nota': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # rellenar el campo de visualización si la instancia ya existe
        if self.instance and getattr(self.instance, 'pk', None):
            self.fields['fecha_registro_display'].initial = getattr(self.instance, 'fecha_registro', None)
        
        # Reordenar campos para una mejor experiencia de usuario
        field_order = [
            'proveedores', 'producto', 'unidad_empaque', 
            'unidades_por_empaque', 'cantidad_empaques', 
            'total_unidades', 'detalle_nota', 'fecha_registro_display'
        ]
        self.fields = {k: self.fields[k] for k in field_order if k in self.fields}

    def clean(self):
        cleaned_data = super().clean()
        unidades_por_empaque = cleaned_data.get('unidades_por_empaque')
        cantidad_empaques = cleaned_data.get('cantidad_empaques')
        
        # Cálculo de respaldo en el servidor si falla el JS
        if cantidad_empaques is not None and cantidad_empaques > 0:
            if not unidades_por_empaque or unidades_por_empaque <= 0:
                self.add_error('unidades_por_empaque', 'Debe especificar un número válido de unidades por empaque.')
            else:
                cleaned_data['total_unidades'] = cantidad_empaques * unidades_por_empaque
        elif cantidad_empaques == 0:
            cleaned_data['total_unidades'] = 0
            
        return cleaned_data

class MovimientosInventarioForm(forms.ModelForm):
    # Sobrescribimos el campo 'producto' para usar nuestro campo personalizado
    producto = ProductoModelChoiceField(
        queryset=Inventario.objects.order_by('nombre_producto'),
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )

    unidades_por_empaque = forms.IntegerField(
        required=False,
        label="Unidades por Empaque",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'placeholder': 'Ej. 12'})
    )

    cantidad_empaques = forms.IntegerField(
        required=False,
        label="Cantidad de Empaques",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'placeholder': 'Ej. 5'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacemos que el campo proveedor no sea requerido a nivel de HTML.
        # La validación real se hará en el método clean().
        self.fields['proveedor'].required = False
        # Hacemos que la cantidad total sea readonly porque se calculará
        self.fields['cantidad'].widget.attrs['readonly'] = True
        self.fields['cantidad'].help_text = "Calculado: Unidades por Empaque x Cantidad de Empaques"

        # Si estamos editando un movimiento, pre-rellenamos el campo 'unidades_por_empaque'
        # para que los cálculos en el frontend y backend funcionen correctamente.
        if self.instance and self.instance.pk:
            if self.instance.cantidad_empaques and self.instance.cantidad_empaques > 0:
                unidades = self.instance.cantidad // self.instance.cantidad_empaques
                self.fields['unidades_por_empaque'].initial = unidades

        # Reordenar campos para una mejor experiencia de usuario
        field_order = [
            'producto', 'tipo_movimiento', 'unidad_empaque', 
            'unidades_por_empaque', 'cantidad_empaques', 'cantidad', 'proveedor'
        ]
        self.fields = {k: self.fields[k] for k in field_order}

    class Meta:
        model = MovimientosInventario
        fields = ['producto', 'tipo_movimiento', 'cantidad_empaques', 'unidad_empaque', 'cantidad', 'proveedor']
        widgets = {
            'proveedor': forms.Select(attrs={'class': 'form-select select2'}),
            'unidad_empaque': forms.Select(attrs={'class': 'form-select'}),
            'tipo_movimiento': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        tipo_movimiento = cleaned_data.get("tipo_movimiento")
        cantidad = cleaned_data.get("cantidad")
        producto = cleaned_data.get("producto")
        proveedor = cleaned_data.get("proveedor")

        unidades_por_empaque = cleaned_data.get('unidades_por_empaque')
        cantidad_empaques = cleaned_data.get("cantidad_empaques")

        # Cálculo de la cantidad total en el backend
        if cantidad_empaques is not None and cantidad_empaques > 0:
            if not unidades_por_empaque or unidades_por_empaque <= 0:
                self.add_error('unidades_por_empaque', 'Debe especificar un número válido de unidades por empaque.')
            else:
                cleaned_data['cantidad'] = cantidad_empaques * unidades_por_empaque
        elif cantidad_empaques == 0:
            cleaned_data['cantidad'] = 0
        
        cantidad = cleaned_data.get("cantidad") # Recargar la cantidad por si fue calculada

        # Validación 1: Si es una SALIDA, verificar que haya stock suficiente.
        if tipo_movimiento == 'SALIDA' and producto and cantidad is not None:
            if cantidad > producto.cantidad:
                raise forms.ValidationError(
                    f"No se puede registrar la salida. Stock insuficiente para '{producto.nombre_producto}'. "
                    f"Disponibles: {producto.cantidad}, se intentó sacar: {cantidad}."
                )

        # Validación 2: Si es una ENTRADA, el proveedor es obligatorio.
        if tipo_movimiento == 'ENTRADA' and not proveedor:
            self.add_error('proveedor', 'Para un movimiento de entrada, es obligatorio seleccionar un proveedor.')

        # Asegurar que si se usó empaques, se guarde la relación
        if cantidad_empaques is None:
            cleaned_data['cantidad_empaques'] = 0

        return cleaned_data

    def save(self, commit=True):
        # Usamos una transacción para asegurar que ambas operaciones (guardar movimiento y actualizar stock)
        # se completen con éxito o ninguna lo haga.
        with transaction.atomic():
            movimiento = super().save(commit=False)
            producto = movimiento.producto
            cantidad_nueva = movimiento.cantidad

            # self.instance.pk será None si es un nuevo movimiento
            if not self.instance.pk:
                # Es un nuevo movimiento
                if movimiento.tipo_movimiento == 'ENTRADA':
                    producto.cantidad += cantidad_nueva
                elif movimiento.tipo_movimiento == 'SALIDA':
                    # La validación ya ocurrió en clean(), aquí solo operamos
                    producto.cantidad -= cantidad_nueva
            else:
                # Es una edición de un movimiento existente
                # Recuperamos los datos originales de la BD porque self.instance ya tiene los cambios en memoria
                movimiento_anterior = MovimientosInventario.objects.get(pk=self.instance.pk)
                cantidad_original = movimiento_anterior.cantidad
                tipo_original = movimiento_anterior.tipo_movimiento

                # 1. Revertir el efecto del movimiento original
                if tipo_original == 'ENTRADA':
                    producto.cantidad -= cantidad_original
                else: # SALIDA
                    producto.cantidad += cantidad_original

                # 2. Aplicar el efecto del nuevo movimiento
                if movimiento.tipo_movimiento == 'ENTRADA':
                    producto.cantidad += cantidad_nueva
                else: # SALIDA
                    if producto.cantidad < cantidad_nueva:
                        # Esta validación es una segunda capa de seguridad por si acaso.
                        # El método clean() ya debería haberlo prevenido.
                        raise forms.ValidationError(f"Stock insuficiente para actualizar la salida de '{producto.nombre_producto}'.")
                    producto.cantidad -= cantidad_nueva
            
            if commit:
                producto.save()
                movimiento.save()
            return movimiento

class UserForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}), required=False, label="Contraseña")
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'username']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellido',
            'email': 'Correo Electrónico',
            'username': 'Nombre de Usuario',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['password'].help_text = "Dejar vacío para mantener la contraseña actual."
        else:
            self.fields['password'].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        password = self.cleaned_data.get('password')
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user

class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ['cedula', 'rol', 'telefono', 'direccion']
        widgets = {
            'cedula': forms.TextInput(attrs={'class': 'form-control'}),
            'rol': forms.Select(attrs={'class': 'form-select'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control'}),
            'direccion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class ImportarArchivoForm(forms.Form):
    archivo = forms.FileField(label="Selecciona un archivo Excel (.xlsx) o CSV (.csv/txt)", widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx, .xls, .csv, .txt'}))