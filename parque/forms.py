from django import forms
from .models import Evento, ProductoParque, ComboParque, Brazalete

class EventoForm(forms.ModelForm):
    total_pagar = forms.DecimalField(required=False, initial=0.00, widget=forms.NumberInput(attrs={'class': 'form-control bg-light fw-bold text-success', 'readonly': 'readonly'}))

    class Meta:
        model = Evento
        fields = [
            'titulo', 'nombre_reserva', 'zona', 'total_pagar', 
            'descripcion', 'fecha_inicio', 'fecha_fin', 'estado', 'responsable'
        ]
        widgets = {
            'fecha_inicio': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'fecha_fin': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_reserva': forms.TextInput(attrs={'class': 'form-control'}),
            'zona': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'responsable': forms.Select(attrs={'class': 'form-select'}),
        }

class ProductoParqueForm(forms.ModelForm):
    class Meta:
        model = ProductoParque
        fields = ['nombre', 'sabor', 'precio']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'sabor': forms.Select(attrs={'class': 'form-select'}),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class ComboParqueForm(forms.ModelForm):
    class Meta:
        model = ComboParque
        fields = ['nombre', 'descripcion', 'precio']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'precio': forms.NumberInput(attrs={'class': 'form-control'}),
        }

class BrazaleteForm(forms.ModelForm):
    class Meta:
        model = Brazalete
        fields = ['nombre', 'cantidad', 'precio']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Combo #1 o Individual'}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'precio': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
