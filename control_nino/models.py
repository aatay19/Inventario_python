from datetime import timedelta
from django.db import models
from django.utils import timezone


TIEMPO_MAXIMO = 180


class ControlNino(models.Model):
    TIEMPO_CHOICES = [
        (1, '1 minuto (prueba)'),
        (45, '45 minutos'),
        (90, '90 minutos'),
    ]

    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    tiempo = models.PositiveIntegerField(choices=TIEMPO_CHOICES, default=90, verbose_name="Tiempo")
    fecha_registro = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Hora de ingreso")
    hora_salida = models.DateTimeField(null=True, blank=True, verbose_name="Hora de salida")

    def __str__(self):
        return f"{self.nombre} ({self.tiempo} min)"

    @property
    def fecha_fin(self):
        return self.fecha_registro + timedelta(minutes=self.tiempo)

    @property
    def hora_salida_estimada(self):
        return self.fecha_fin

    @property
    def minutos_estancia(self):
        """Minutos que el niño permaneció, sin superar el tiempo contratado."""
        fin = self.hora_salida or timezone.now()
        transcurridos = max(0, int((fin - self.fecha_registro).total_seconds() // 60))
        return min(self.tiempo, transcurridos)

    @property
    def salio(self):
        return self.hora_salida is not None

    @property
    def segundos_restantes(self):
        return int((self.fecha_fin - timezone.now()).total_seconds())

    @property
    def minutos_restantes(self):
        return self.segundos_restantes / 60

    @property
    def inicio_ms(self):
        return int(self.fecha_registro.timestamp() * 1000)

    @property
    def color_estado(self):
        restante = self.minutos_restantes
        if restante <= 0:
            return 'rojo'
        if restante > 45:
            return 'verde'
        return 'amarillo'

    class Meta:
        verbose_name = "Control de Niño"
        verbose_name_plural = "Control de Niños"
        ordering = ['fecha_registro']


class Fiesta(models.Model):
    TIEMPO_CHOICES = ControlNino.TIEMPO_CHOICES

    nombre = models.CharField(max_length=100, verbose_name="Nombre de la fiesta")
    tiempo = models.PositiveIntegerField(choices=TIEMPO_CHOICES, default=90, verbose_name="Tiempo general (min)")
    fecha_registro = models.DateTimeField(auto_now_add=True, db_index=True, verbose_name="Hora de ingreso")
    hora_inicio = models.DateTimeField(null=True, blank=True, verbose_name="Hora de inicio del tiempo")
    hora_salida = models.DateTimeField(null=True, blank=True, verbose_name="Hora de salida")

    def __str__(self):
        return f"{self.nombre} ({self.brazaletes.count()} brazaletes)"

    @property
    def cantidad_brazaletes(self):
        return self.brazaletes.count()

    @property
    def iniciada(self):
        return self.hora_inicio is not None

    @property
    def salio(self):
        return self.hora_salida is not None

    @property
    def puede_agregar_45(self):
        return not self.salio and self.tiempo + 45 <= TIEMPO_MAXIMO

    @property
    def puede_agregar_90(self):
        return not self.salio and self.tiempo + 90 <= TIEMPO_MAXIMO

    @property
    def tiempo_maximo_alcanzado(self):
        return not self.salio and self.tiempo >= TIEMPO_MAXIMO

    @property
    def todos_brazaletes_completos(self):
        brazaletes = list(self.brazaletes.all())
        return bool(brazaletes) and all((b.nombre or '').strip() for b in brazaletes)

    @property
    def resumen_brazaletes(self):
        nombres = [b.nombre.strip() for b in self.brazaletes.all() if (b.nombre or '').strip()]
        if nombres:
            return ', '.join(nombres)
        return f"{self.cantidad_brazaletes} brazaletes"

    @property
    def fecha_fin(self):
        if not self.hora_inicio:
            return None
        return self.hora_inicio + timedelta(minutes=self.tiempo)

    @property
    def segundos_restantes(self):
        if not self.fecha_fin:
            return None
        return int((self.fecha_fin - timezone.now()).total_seconds())

    @property
    def minutos_restantes(self):
        seg = self.segundos_restantes
        return None if seg is None else seg / 60

    @property
    def inicio_ms(self):
        if not self.hora_inicio:
            return None
        return int(self.hora_inicio.timestamp() * 1000)

    @property
    def color_estado(self):
        if self.salio or not self.iniciada:
            return 'gris'
        restante = self.minutos_restantes
        if restante <= 0:
            return 'rojo'
        if restante > 45:
            return 'verde'
        return 'amarillo'

    class Meta:
        verbose_name = "Fiesta"
        verbose_name_plural = "Fiestas"
        ordering = ['-fecha_registro']


class BrazaleteFiesta(models.Model):
    fiesta = models.ForeignKey(Fiesta, on_delete=models.CASCADE, related_name='brazaletes')
    numero = models.PositiveIntegerField(default=1, verbose_name="N° de brazalete")
    nombre = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")

    def __str__(self):
        return f"Brazalete #{self.numero} de {self.fiesta.nombre}"

    class Meta:
        verbose_name = "Brazalete de Fiesta"
        verbose_name_plural = "Brazaletes de Fiesta"
        ordering = ['numero']
