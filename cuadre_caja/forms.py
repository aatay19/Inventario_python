from decimal import Decimal

from django import forms
from django.utils import timezone

from .models import (
    Caja,
    CierreCaja,
    Departamento,
    EgresoCierre,
    ImagenCierre,
    MONEDA_BS,
    MONEDA_POR_METODO,
    MONEDA_USD,
    MetodoPagoChoices,
    TipoSalidaChoices,
    TurnoChoices,
    CierreTransaccion,
)


class CierreCajaForm(forms.ModelForm):
    """Registro del cierre diario: datos generales y montos por método."""

    class Meta:
        model = CierreCaja
        fields = ["turno", "nombre_cajera", "tasa", "observaciones"]
        widgets = {
            "turno": forms.Select(attrs={"class": "form-select"}),
            "nombre_cajera": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre y apellido de la cajera",
                }
            ),
            "tasa": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.0001",
                    "min": "0.0001",
                    "placeholder": "0.0000",
                }
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Novedades, faltantes, observaciones...",
                }
            ),
        }
        labels = {
            "turno": "Turno",
            "nombre_cajera": "Nombre de la cajera",
            "tasa": "Tasa del día (Bs por USD)",
            "observaciones": "Observaciones",
        }

    def __init__(self, *args, caja=None, **kwargs):
        self.caja = caja
        super().__init__(*args, **kwargs)

        # La fecha no se elige: se toma del servidor al momento de registrar.
        self.fecha = self.instance.fecha if self.instance.pk else timezone.localdate()

        # Inicializar turno
        if not self.is_bound:
            self.fields["turno"].initial = (
                TurnoChoices.AM if timezone.localtime().hour < 12 else TurnoChoices.PM
            )

        for valor, etiqueta in MetodoPagoChoices.choices:
            moneda = MONEDA_POR_METODO[valor]
            simbolo = "USD" if moneda == MONEDA_USD else "Bs"
            self.fields[f"monto_{valor}"] = forms.DecimalField(
                label=f"{etiqueta} ({simbolo})",
                required=False,
                max_digits=14,
                decimal_places=2,
                min_value=0,
                initial=0,
                widget=forms.NumberInput(
                    attrs={
                        "class": "form-control form-control-sm text-end monto-cierre",
                        "step": "0.01",
                        "min": "0",
                        "placeholder": "0.00",
                        "data-moneda": moneda.lower(),
                        "data-metodo": valor,
                        "readonly": True,
                    }
                ),
            )

    def clean(self):
        cleaned_data = super().clean()
        fecha = self.fecha
        turno = cleaned_data.get("turno")

        if self.caja and fecha and turno:
            existentes = CierreCaja.objects.filter(
                caja=self.caja,
                fecha=fecha,
                turno=turno,
            )
            if self.instance.pk:
                existentes = existentes.exclude(pk=self.instance.pk)
            if existentes.exists():
                raise forms.ValidationError(
                    f"Ya existe un cierre para {self.caja.nombre} el "
                    f"{fecha:%d/%m/%Y} en el turno {turno}."
                )

        return cleaned_data

    def montos_por_metodo(self):
        """Devuelve {metodo: {'bs': Decimal, 'usd': Decimal}} según su moneda."""
        montos = {}
        for valor, _ in MetodoPagoChoices.choices:
            monto = self.cleaned_data.get(f"monto_{valor}") or Decimal("0.00")
            if MONEDA_POR_METODO[valor] == MONEDA_USD:
                montos[valor] = {"bs": Decimal("0.00"), "usd": monto}
            else:
                montos[valor] = {"bs": monto, "usd": Decimal("0.00")}
        return montos


class EgresoCierreForm(forms.ModelForm):
    """Fila de egreso o devolución dentro del cierre."""

    tipo = forms.ChoiceField(
        label="Tipo",
        required=False,
        choices=[("", "Tipo")] + list(TipoSalidaChoices.choices),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    cedula = forms.CharField(
        label="Cédula",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "V-12345678",
            }
        ),
    )
    telefono = forms.CharField(
        label="Teléfono",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "0414-1234567",
            }
        ),
    )
    banco = forms.CharField(
        label="Banco",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Banco",
            }
        ),
    )
    moneda = forms.ChoiceField(
        label="Moneda",
        required=False,
        choices=[
            ("", "Moneda"),
            (MONEDA_BS, "Bolívares (Bs)"),
            (MONEDA_USD, "Dólares (USD)"),
        ],
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    monto = forms.DecimalField(
        label="Monto",
        required=False,
        max_digits=14,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-sm text-end",
                "step": "0.01",
                "min": "0",
                "placeholder": "0.00",
            }
        ),
    )
    referencia = forms.CharField(
        label="Referencia",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Nro. de referencia",
            }
        ),
    )

    class Meta:
        model = EgresoCierre
        fields = [
            "tipo",
            "cedula",
            "telefono",
            "banco",
            "moneda",
            "monto",
            "referencia",
        ]

    def has_changed(self):
        """Ignora las filas completamente vacías del formset."""
        if not self.is_bound:
            return False
        return any(
            (self.data.get(self.add_prefix(campo)) or "").strip()
            for campo in (
                "tipo",
                "cedula",
                "telefono",
                "banco",
                "moneda",
                "monto",
                "referencia",
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        tipo = cleaned_data.get("tipo")
        moneda = cleaned_data.get("moneda")
        monto = cleaned_data.get("monto")
        datos = [
            (cleaned_data.get(campo) or "").strip()
            for campo in ("cedula", "telefono", "banco", "referencia")
        ]

        if not any([tipo, moneda, monto, *datos]):
            return cleaned_data

        if not tipo:
            self.add_error("tipo", "Selecciona si es egreso o devolución.")
        if not moneda:
            self.add_error("moneda", "Selecciona la moneda.")
        if monto is None or monto <= 0:
            self.add_error("monto", "El monto debe ser mayor a cero.")

        return cleaned_data


EgresoCierreFormSet = forms.inlineformset_factory(
    CierreCaja,
    EgresoCierre,
    form=EgresoCierreForm,
    extra=1,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class CierreTransaccionForm(forms.ModelForm):
    """Fila de transacción (banco, monto, ref, notas, formato de billetes) dentro del cierre."""

    metodo_pago = forms.ChoiceField(
        label="Método de pago",
        required=False,
        choices=[("", "Método")] + list(MetodoPagoChoices.choices),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    banco = forms.CharField(
        label="Banco o entidad",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Banco o entidad",
            }
        ),
    )
    monto = forms.DecimalField(
        label="Monto",
        required=False,
        max_digits=14,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-sm text-end",
                "step": "0.01",
                "min": "0",
                "placeholder": "0.00",
            }
        ),
    )
    ref = forms.CharField(
        label="Referencia",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Número de referencia",
            }
        ),
    )
    notas = forms.CharField(
        label="Notas",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Notas adicionales",
            }
        ),
    )
    formato_billetes_bs = forms.ChoiceField(
        label="Formato billetes Bs",
        required=False,
        choices=[
            ("", "Selecciona"),
            ("10", "10"),
            ("20", "20"),
            ("50", "50"),
            ("100", "100"),
            ("200", "200"),
            ("500", "500"),
        ],
        initial="",
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )

    class Meta:
        model = CierreTransaccion
        fields = ["metodo_pago", "banco", "monto", "ref", "notas", "formato_billetes_bs"]

    def has_changed(self):
        """Ignora las filas completamente vacías del formset."""
        if not self.is_bound:
            return False
        return any(
            (self.data.get(self.add_prefix(campo)) or "").strip()
            for campo in ("metodo_pago", "banco", "monto", "ref", "notas", "formato_billetes_bs")
        )

    def clean(self):
        cleaned_data = super().clean()
        metodo = cleaned_data.get("metodo_pago")
        banco = (cleaned_data.get("banco") or "").strip()
        monto = cleaned_data.get("monto")
        ref = (cleaned_data.get("ref") or "").strip()
        notas = (cleaned_data.get("notas") or "").strip()
        formato = (cleaned_data.get("formato_billetes_bs") or "").strip()

        if not any([metodo, banco, monto, ref]):
            return cleaned_data

        if not metodo:
            self.add_error("metodo_pago", "Selecciona un método de pago.")
        if monto is None or monto <= 0:
            self.add_error("monto", "El monto debe ser mayor a cero.")

        return cleaned_data


CierreTransaccionFormSet = forms.inlineformset_factory(
    CierreCaja,
    CierreTransaccion,
    form=CierreTransaccionForm,
    extra=1,
    can_delete=False,
    min_num=0,
    validate_min=False,
)


class ImagenCierreForm(forms.ModelForm):
    """Imagen adjunta a un cierre, con un título descriptivo."""

    titulo = forms.CharField(
        label="Título",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control form-control-sm",
                "placeholder": "Título de la imagen",
            }
        ),
    )
    imagen = forms.ImageField(
        label="Imagen",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control form-control-sm", "accept": "image/*"}
        ),
    )

    class Meta:
        model = ImagenCierre
        fields = ["titulo", "imagen"]

    def has_changed(self):
        """Ignora las filas completamente vacías del formset."""
        if not self.is_bound:
            return False
        titulo = (self.data.get(self.add_prefix("titulo")) or "").strip()
        imagen = self.files.get(self.add_prefix("imagen"))
        return bool(titulo or imagen)

    def clean(self):
        cleaned_data = super().clean()
        titulo = (cleaned_data.get("titulo") or "").strip()
        imagen = cleaned_data.get("imagen")

        if not titulo and not imagen:
            return cleaned_data

        if not titulo:
            self.add_error("titulo", "Indica un título para la imagen.")
        if not imagen:
            self.add_error("imagen", "Selecciona una imagen.")

        return cleaned_data


ImagenCierreFormSet = forms.inlineformset_factory(
    CierreCaja,
    ImagenCierre,
    form=ImagenCierreForm,
    extra=1,
    max_num=5,
    validate_max=True,
    can_delete=True,
    min_num=0,
    validate_min=False,
)


class CierreHistorialFiltroForm(forms.Form):
    departamento = forms.ModelChoiceField(
        label="Departamento",
        queryset=Departamento.objects.none(),
        required=False,
        empty_label="Todos los departamentos",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    turno = forms.ChoiceField(
        label="Turno",
        required=False,
        choices=[("", "Todos los turnos")] + list(TurnoChoices.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cajera = forms.CharField(
        label="Cajera",
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Nombre de la cajera"}
        ),
    )
    desde = forms.DateField(
        label="Desde",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    hasta = forms.DateField(
        label="Hasta",
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["departamento"].queryset = Departamento.objects.filter(activo=True)


class ReporteFiltroForm(forms.Form):
    """Filtros del reporte: periodo, fecha de referencia, departamento, caja y turno."""

    PERIODO_DIA = "DIA"
    PERIODO_SEMANA = "SEMANA"
    PERIODO_MES = "MES"
    PERIODO_ANIO = "ANIO"

    PERIODO_CHOICES = [
        (PERIODO_DIA, "Día"),
        (PERIODO_SEMANA, "Semana"),
        (PERIODO_MES, "Mensual"),
        (PERIODO_ANIO, "Anual"),
    ]

    periodo = forms.ChoiceField(
        label="Periodo",
        choices=PERIODO_CHOICES,
        initial=PERIODO_DIA,
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    fecha = forms.DateField(
        label="Fecha de referencia",
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(
            format="%Y-%m-%d",
            attrs={"class": "form-control", "type": "date"},
        ),
    )
    departamento = forms.ModelChoiceField(
        label="Departamento",
        queryset=Departamento.objects.none(),
        required=False,
        empty_label="Todos los departamentos",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    caja = forms.ModelChoiceField(
        label="Caja",
        queryset=Caja.objects.none(),
        required=False,
        empty_label="Todas las cajas",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    turno = forms.ChoiceField(
        label="Turno",
        required=False,
        choices=[("", "Todos los turnos")] + list(TurnoChoices.choices),
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["departamento"].queryset = Departamento.objects.filter(activo=True)
        self.fields["caja"].queryset = Caja.objects.filter(activo=True).select_related(
            "departamento"
        ).order_by("departamento__orden", "departamento__nombre", "numero")
