from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Cliente(models.Model):
    id= models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, verbose_name="Nombre y Apellido")
    email = models.EmailField(unique=True, verbose_name="Email")
    telefono = models.CharField(max_length=15, verbose_name="Numero de telefono")
    cedula = models.IntegerField( verbose_name="Cedula",unique=True)
    direccion = models.TextField()

    def __str__(self):
        fila= "id: " + str(self.id) + " - " + self.nombre + " - " + self.email + " - " + self.telefono + " - " + self.cedula + " - " + self.direccion
        return fila


class Proveedor(models.Model):
    id= models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Proveedor")
    telefono = models.CharField(max_length=15, verbose_name="Numero de telefono")
    razonsocial = models.CharField(max_length=150, verbose_name="Razon Social")
    rif = models.CharField(max_length=20, verbose_name="RIF", unique=True)
    direccion = models.TextField()
    dias_descuentos = models.CharField(
        max_length=150,
        blank=True,
        verbose_name="Días de Descuentos",
        help_text="Ej: Lunes, Miércoles y Viernes"
    )

    def __str__(self):
        fila= "id: " + str(self.id) + " - " + self.nombre + " - " + self.telefono + " - " + self.razonsocial + " - " + self.rif + " - " + self.direccion
        return fila
    

class HistorialProveedoresNotas(models.Model):
    """Notas históricas, acuerdos y condiciones comerciales con el proveedor."""
    id_historialproveedor = models.AutoField(primary_key=True)
    proveedores = models.ForeignKey(Proveedor, on_delete=models.CASCADE, verbose_name=("Proveedor"))
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name=("Fecha de Registro"))
    detalle_nota = models.TextField(verbose_name=("Detalle de Nota"))

    def __str__(self):
        # mostrar proveedor + fecha + inicio de la nota
        proveedor_nombre = self.proveedores.nombre if self.proveedores else "Sin proveedor"
        resumen = (self.detalle_nota[:60] + '...') if self.detalle_nota and len(self.detalle_nota) > 60 else (self.detalle_nota or '')
        return f"{proveedor_nombre} — {self.fecha_registro:%Y-%m-%d} — {resumen}"

    class Meta:
        verbose_name = ("Nota de Proveedor")
        verbose_name_plural = ("Historial de Notas de Proveedores")
        ordering = ['-fecha_registro']        

class CategoriaChoices(models.TextChoices):
    ELECTRONICA = 'ELECTRONICA', 'electrónica'
    ROPA = 'ROPA', 'Ropa'
    ALIMENTACION = 'ALIMENTACION', 'Alimentación'
    HOGAR = 'HOGAR', 'Hogar'
    OTRO = 'OTRO', 'Otro'
    BEBIDAS = 'BEBIDAS', 'Bebidas'


class Inventario(models.Model):
    id_producto = models.AutoField(primary_key=True)
    codigo_producto = models.CharField(
        max_length=20,
        unique=True,
        null=True,      # inicialmente True para migración segura
        blank=True,
        verbose_name="Código del Producto",
        help_text="Código interno único (p. ej. SKU)."
    )
    nombre_producto = models.CharField(max_length=100, verbose_name="Nombre del Producto")
    descripcion = models.TextField(verbose_name="Descripcion del Producto")
    categoria = models.CharField(
        max_length=20,
        choices=CategoriaChoices.choices,
        default=CategoriaChoices.OTRO,
        verbose_name="Categoria del Producto"
    )
    cantidad = models.IntegerField(verbose_name="Cantidad en Stock")
    costo_actual = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Costo Actual")
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de Venta") 
    stock_minimo = models.IntegerField(verbose_name="Stock Minimo")
    stock_maximo = models.IntegerField(verbose_name="Stock Maximo")

    def __str__(self):
        fila= "id: " + str(self.id_producto) + " - " + str(self.codigo_producto) + " - " + self.nombre_producto + " - " + self.descripcion + " - " + str(self.cantidad) + " - " + str(self.costo_actual) + " - " + str(self.precio_venta) + " - " + str(self.stock_minimo) + " - " + str(self.stock_maximo)
        return fila   
    
class MovimientosInventario(models.Model):
    TIPO_MOVIMIENTO_CHOICES = [
        ('ENTRADA', 'Entrada'),
        ('SALIDA', 'Salida'),
    ]

    id_movimiento = models.AutoField(primary_key=True)
    producto = models.ForeignKey(Inventario, on_delete=models.CASCADE, verbose_name="Producto")
    tipo_movimiento = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO_CHOICES, verbose_name="Tipo de Movimiento")
    cantidad = models.IntegerField(verbose_name="Cantidad")
    fecha_movimiento = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Movimiento")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Proveedor")

    def __str__(self):
        return f"{self.tipo_movimiento} - {self.producto.nombre_producto} - {self.cantidad} unidades el {self.fecha_movimiento:%Y-%m-%d}"

class PerfilUsuario(models.Model):
    ROL_CHOICES = [
        ('admin', 'Administrador'),
        ('almacenista', 'Almacenista'),
        ('vendedor', 'Vendedor'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Usuario")
    cedula = models.CharField(max_length=20, unique=True, null=True, blank=True, verbose_name="Cédula")
    rol = models.CharField(max_length=20, choices=ROL_CHOICES, default='vendedor', verbose_name="Rol")
    telefono = models.CharField(max_length=20, blank=True, verbose_name="Teléfono")
    direccion = models.TextField(blank=True, verbose_name="Dirección")
    foto = models.ImageField(upload_to='perfiles/', blank=True, null=True, verbose_name="Foto de Perfil")

    def __str__(self):
        return f"Perfil de {self.user.username}"

    class Meta:
        verbose_name = "Perfil de Usuario"
        verbose_name_plural = "Perfiles de Usuarios"

@receiver(post_save, sender=User)
def crear_perfil_usuario(sender, instance, created, **kwargs):
    if created:
        PerfilUsuario.objects.create(user=instance)

@receiver(post_save, sender=User)
def guardar_perfil_usuario(sender, instance, **kwargs):
    if not hasattr(instance, 'perfilusuario'):
        PerfilUsuario.objects.create(user=instance)
    else:
        instance.perfilusuario.save()