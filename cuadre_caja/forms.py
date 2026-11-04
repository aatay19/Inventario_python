from decimal import Decimal

from django import forms
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    Caja,
    CierreCaja,
    Departamento,
    EgresoGeneral,
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


BANCOS_CHOICES = [
    ("", "Banco"),
    ("Banesco", "Banesco"),
    ("Mercantil", "Mercantil"),
    ("Venezuela", "Venezuela"),
]


class DepartamentoForm(forms.ModelForm):
    """Registro y edición de un departamento."""

    slug = forms.SlugField(
        label="Identificador",
        required=False,
        help_text="Si lo dejas vacío se genera desde el nombre.",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "supermercado",
            }
        ),
    )

    class Meta:
        model = Departamento
        fields = ["nombre", "slug", "orden", "activo"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre del departamento",
                }
            ),
            "orden": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "placeholder": "0",
                }
            ),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if not slug:
            slug = slugify(self.cleaned_data.get("nombre", ""))
        if not slug:
            raise forms.ValidationError("Indica un identificador para el departamento.")

        existentes = Departamento.objects.filter(slug=slug)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError(
                "Ya existe un departamento con ese identificador."
            )
        return slug


class CajaForm(forms.ModelForm):
    """Registro de una caja dentro de un departamento."""

    class Meta:
        model = Caja
        fields = ["nombre", "numero", "activo"]
        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre de la caja",
                }
            ),
            "numero": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "1",
                    "placeholder": "1",
                }
            ),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, departamento=None, **kwargs):
        self.departamento = departamento
        super().__init__(*args, **kwargs)
        if departamento and not self.instance.pk and not self.initial.get("numero"):
            ultimo = (
                Caja.objects.filter(departamento=departamento)
                .order_by("-numero")
                .values_list("numero", flat=True)
                .first()
            )
            self.initial["numero"] = (ultimo or 0) + 1

    def clean_numero(self):
        numero = self.cleaned_data.get("numero")
        if self.departamento and numero:
            existentes = Caja.objects.filter(
                departamento=self.departamento, numero=numero
            )
            if self.instance.pk:
                existentes = existentes.exclude(pk=self.instance.pk)
            if existentes.exists():
                raise forms.ValidationError(
                    "Ya existe una caja con ese número en este departamento."
                )
        return numero


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
    banco = forms.ChoiceField(
        label="Banco",
        required=False,
        choices=BANCOS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
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
    imagen = forms.ImageField(
        label="Imagen",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control form-control-sm", "accept": "image/*"}
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
            "imagen",
        ]

    def has_changed(self):
        """Ignora las filas completamente vacías del formset."""
        if not self.is_bound:
            return False
        if self.files.get(self.add_prefix("imagen")):
            return True
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
        imagen = cleaned_data.get("imagen")
        datos = [
            (cleaned_data.get(campo) or "").strip()
            for campo in ("cedula", "telefono", "banco", "referencia")
        ]

        if not any([tipo, moneda, monto, imagen, *datos]):
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


class EgresoGeneralForm(forms.ModelForm):
    """Registro independiente de un egreso o devolución, con motivo."""

    tipo = forms.ChoiceField(
        label="Tipo",
        required=True,
        choices=TipoSalidaChoices.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    cedula = forms.CharField(
        label="Cédula",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "V-12345678",
            }
        ),
    )
    telefono = forms.CharField(
        label="Teléfono",
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "0414-1234567",
            }
        ),
    )
    banco = forms.ChoiceField(
        label="Banco",
        required=False,
        choices=BANCOS_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    moneda = forms.ChoiceField(
        label="Moneda",
        required=True,
        choices=[
            (MONEDA_BS, "Bolívares (Bs)"),
            (MONEDA_USD, "Dólares (USD)"),
        ],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    monto = forms.DecimalField(
        label="Monto",
        required=True,
        max_digits=14,
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control text-end",
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
                "class": "form-control",
                "placeholder": "Nro. de referencia",
            }
        ),
    )
    imagen = forms.ImageField(
        label="Imagen",
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": "image/*"}
        ),
    )
    motivo = forms.CharField(
        label="Motivo",
        required=True,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Motivo del egreso o devolución",
            }
        ),
    )

    class Meta:
        model = EgresoGeneral
        fields = [
            "tipo",
            "cedula",
            "telefono",
            "banco",
            "moneda",
            "monto",
            "referencia",
            "imagen",
            "motivo",
        ]

    def clean_monto(self):
        monto = self.cleaned_data.get("monto")
        if monto is not None and monto <= 0:
            raise forms.ValidationError("El monto debe ser mayor a cero.")
        return monto


class CierreTransaccionForm(forms.ModelForm):
    """Fila de transacción (banco, monto, referencia y notas) dentro del cierre."""

    metodo_pago = forms.ChoiceField(
        label="Método de pago",
        required=False,
        choices=[("", "Método")] + list(MetodoPagoChoices.choices),
        widget=forms.Select(attrs={"class": "form-select form-select-sm"}),
    )
    banco = forms.ChoiceField(
        label="Banco o entidad",
        required=False,
        choices=BANCOS_CHOICES,
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

    class Meta:
        model = CierreTransaccion
        fields = ["metodo_pago", "banco", "monto", "ref", "notas"]

    def has_changed(self):
        """Ignora las filas completamente vacías del formset."""
        if not self.is_bound:
            return False
        return any(
            (self.data.get(self.add_prefix(campo)) or "").strip()
            for campo in ("metodo_pago", "banco", "monto", "ref", "notas")
        )

    def clean(self):
        cleaned_data = super().clean()
        metodo = cleaned_data.get("metodo_pago")
        banco = (cleaned_data.get("banco") or "").strip()
        monto = cleaned_data.get("monto")
        ref = (cleaned_data.get("ref") or "").strip()

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
