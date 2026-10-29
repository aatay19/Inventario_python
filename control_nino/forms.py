from django import forms
from django.forms import inlineformset_factory
from .models import ControlNino, Fiesta, BrazaleteFiesta, Novedad


class ControlNinoForm(forms.ModelForm):
    class Meta:
        model = ControlNino
        fields = ['nombre', 'descripcion', 'tiempo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del niño'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción, características o contacto...'}),
            'tiempo': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre': 'Nombre',
            'descripcion': 'Descripción',
            'tiempo': 'Tiempo',
        }


class FiestaForm(forms.ModelForm):
    cantidad_brazaletes = forms.IntegerField(
        min_value=1, max_value=500, initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 500}),
        label="Cantidad de brazaletes"
    )

    class Meta:
        model = Fiesta
        fields = ['nombre', 'tiempo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cumpleaños de Ana'}),
            'tiempo': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'nombre': 'Nombre de la fiesta',
            'tiempo': 'Tiempo general',
        }


class BrazaleteFiestaForm(forms.ModelForm):
    class Meta:
        model = BrazaleteFiesta
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Nombre de quien usa el brazalete'}),
            'descripcion': forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Descripción / observación'}),
        }


BrazaleteFiestaFormSet = inlineformset_factory(
    Fiesta, BrazaleteFiesta,
    form=BrazaleteFiestaForm,
    fields=['nombre', 'descripcion'],
    extra=0, can_delete=False
)


class NovedadManualForm(forms.ModelForm):
    class Meta:
        model = Novedad
        fields = ['titulo', 'descripcion', 'nino', 'fiesta']
        widgets = {
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Incidente en área de juegos, objeto extraviado...'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Describe lo sucedido con el mayor detalle posible...'}),
            'nino': forms.Select(attrs={'class': 'form-select'}),
            'fiesta': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'titulo': 'Título / Asunto',
            'descripcion': 'Descripción de la novedad',
            'nino': 'Niño involucrado (opcional)',
            'fiesta': 'Fiesta involucrada (opcional)',
        }
