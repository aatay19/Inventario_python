from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Brazalete(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre (ej: Combo #1)")
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad de Brazaletes que incluye", default=1)
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio ($)")

    def __str__(self):
        return f"{self.nombre} - ${self.precio}"

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
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    sabor = models.CharField(max_length=10, choices=SABOR_CHOICES, default='NINGUNO', verbose_name="Sabor")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio de Venta")
    existencia = models.IntegerField(default=0, verbose_name="Stock/Existencia")
    fecha_registro = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombre} ({self.get_sabor_display()})"

    class Meta:
        verbose_name = "Producto del Parque"
        verbose_name_plural = "Productos del Parque"

class ComboParque(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Combo")
    descripcion = models.TextField(blank=True, null=True, verbose_name="¿Qué incluye?")
    productos = models.ManyToManyField(ProductoParque, verbose_name="Productos incluidos")
    precio = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Precio del Combo")
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Combo del Parque"
        verbose_name_plural = "Combos del Parque"

class Evento(models.Model):
    ESTADO_CHOICES = [
        ('PROGRAMADO', 'Programado'),
        ('EN_CURSO', 'En Curso'),
        ('FINALIZADO', 'Finalizado'),
        ('CANCELADO', 'Cancelado'),
    ]

    titulo = models.CharField(max_length=150, verbose_name="Título del Evento")
    nombre_reserva = models.CharField(max_length=100, verbose_name="Nombre de la Reserva", null=True, blank=True)
    zona = models.CharField(max_length=100, verbose_name="Zona/Área", null=True, blank=True)
    
    total_pagar = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Total a Pagar")
    
    descripcion = models.TextField(verbose_name="Descripción General", blank=True, null=True)
    fecha_inicio = models.DateTimeField(default=timezone.now)
    fecha_fin = models.DateTimeField(blank=True, null=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PROGRAMADO')
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Responsable")

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

    def save(self, *args, **kwargs):
        self.subtotal = self.cantidad * self.precio_unitario
        super().save(*args, **kwargs)

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
