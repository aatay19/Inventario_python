from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Brazalete(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre (ej: Combo #1)")
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad de Brazaletes que incluye", default=1)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Configuración de Brazalete"
        verbose_name_plural = "Configuración de Brazaletes"

class ProductoParque(models.Model):
    SABOR_CHOICES = [
        ('DULCE', 'Dulce'),
        ('SALADO', 'Salado'),
        ('BEBIDA', 'Bebida'),
        ('NINGUNO', 'N/A'),
    ]

    nombre = models.CharField(max_length=100, verbose_name="Nombre del Producto")
    sabor = models.CharField(max_length=10, choices=SABOR_CHOICES, default='NINGUNO', verbose_name="Sabor")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_sabor_display()})"

    class Meta:
        verbose_name = "Producto del Parque"
        verbose_name_plural = "Productos del Parque"

class ComboParque(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Combo")
    descripcion = models.TextField(blank=True, null=True, verbose_name="¿Qué incluye?")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Combo del Parque"
        verbose_name_plural = "Combos del Parque"

class ProductoEnCombo(models.Model):
    combo = models.ForeignKey(ComboParque, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(ProductoParque, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} en {self.combo.nombre}"

class Evento(models.Model):
    ESTADO_CHOICES = [
        ('PROGRAMADO', 'Programado'),
        ('EN_CURSO', 'En Curso'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]

    ZONA_CHOICES = [
        ('PULPO', 'Pulpo'),
        ('PARED_BLANCA', 'Pared blanca'),
        ('VENTANA', 'Ventana'),
    ]
    METODO_PAGO_CHOICES = [
        ('DIVISA', 'Divisa'),
        ('ZELLE', 'Zelle'),
        ('PAGO_MOVIL', 'Pago móvil'),
        ('PUNTO_VENTA', 'Punto de venta'),
        ('BIO_PAGO', 'Bio pago'),
        ('EFECTIVO_BS', 'Efectivo Bolívares'),
    ]

    titulo = models.CharField(max_length=150, verbose_name="Título del Evento")
    nombre_reserva = models.CharField(max_length=100, verbose_name="Nombre de la Reserva", null=True, blank=True)
    zona = models.CharField(max_length=100, choices=ZONA_CHOICES, verbose_name="Zona/Área", null=True, blank=True)
    
    # Abono 1
    fecha_abono1 = models.DateField(verbose_name="Fecha de Abono 1", null=True, blank=True)
    monto_abono1 = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto Abono 1", null=True, blank=True)
    metodo_pago = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, verbose_name="Método de Pago (Abono 1)", null=True, blank=True)
    nota_forma_pago = models.CharField(max_length=255, verbose_name="Nota de Forma Pagos (Abono 1)", null=True, blank=True)

    # Abono 2
    fecha_abono2 = models.DateField(verbose_name="Fecha de Abono 2", null=True, blank=True)
    monto_abono2 = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto Abono 2", null=True, blank=True)
    metodo_pago2 = models.CharField(max_length=20, choices=METODO_PAGO_CHOICES, verbose_name="Método de Pago (Abono 2)", null=True, blank=True)
    nota_forma_pago2 = models.CharField(max_length=255, verbose_name="Nota de Forma Pagos (Abono 2)", null=True, blank=True)
    
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Total a Pagar")
    
    descripcion = models.TextField(verbose_name="Descripción General", blank=True, null=True)
    fecha_inicio = models.DateField(default=timezone.now, verbose_name="Fecha de Reserva")
    hora_inicio = models.TimeField(null=True, blank=True, verbose_name="Hora de Inicio")
    duracion_horas = models.PositiveIntegerField(default=1, verbose_name="Duración (Horas)")
    fecha_fin = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PROGRAMADO')

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

class DetalleEvento(models.Model):
    TIPO_CHOICES = [
        ('BRAZALETE', 'Brazalete'),
        ('PRODUCTO', 'Producto'),
        ('COMBO', 'Combo'),
    ]
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='detalles')
    tipo_item = models.CharField(max_length=20, choices=TIPO_CHOICES)
    item_id = models.PositiveIntegerField()
    nombre_item = models.CharField(max_length=150)
    cantidad = models.PositiveIntegerField(default=1)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad}x {self.nombre_item} en {self.evento.titulo}"

class HistorialEvento(models.Model):
    evento = models.ForeignKey(Evento, on_delete=models.CASCADE, related_name='historial')
    fecha_registro = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    observacion = models.TextField(verbose_name="Observación/Cambio")
    accion = models.CharField(max_length=100, verbose_name="Acción Realizada") # Ej: Creación, Cambio de Estado, Nota

    def __str__(self):
        return f"Historial de {self.evento.titulo} - {self.fecha_registro.strftime('%d/%m/%Y %H:%M')}"

    class Meta:
        ordering = ['-fecha_registro']
