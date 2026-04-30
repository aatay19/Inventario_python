from django import forms
from .models import Evento, ProductoParque, ComboParque, Brazalete

class EventoForm(forms.ModelForm):
    total_pagar = forms.DecimalField(required=False, initial=0.00, widget=forms.NumberInput(attrs={'class': 'form-control bg-light fw-bold text-success', 'readonly': 'readonly'}))

    class Meta:
        model = Evento
        fields = [
            'titulo', 'nombre_reserva', 'zona', 'metodo_pago', 'nota_forma_pago', 'total_pagar', 
            'descripcion', 'fecha_inicio', 'hora_inicio', 'duracion_horas', 'estado'
        ]
        widgets = {
            'fecha_inicio': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'hora_inicio': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'duracion_horas': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_reserva': forms.TextInput(attrs={'class': 'form-control'}),
            'zona': forms.Select(attrs={'class': 'form-select'}),
            'metodo_pago': forms.Select(attrs={'class': 'form-select'}),
            'nota_forma_pago': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nota sobre la forma de pago...'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
        }

class ProductoParqueForm(forms.ModelForm):
    class Meta:
        model = ProductoParque
        fields = ['nombre', 'sabor']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'sabor': forms.Select(attrs={'class': 'form-select'}),
        }

class ComboParqueForm(forms.ModelForm):
    class Meta:
        model = ComboParque
        fields = ['nombre', 'descripcion']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class BrazaleteForm(forms.ModelForm):
    class Meta:
        model = Brazalete
        fields = ['nombre', 'cantidad']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Combo #1 o Individual'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }
