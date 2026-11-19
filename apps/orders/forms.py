from django import forms

from .models import GarantiaReclamo


class GarantiaForm(forms.Form):
    ventaId = forms.IntegerField(min_value=1)
    productoId = forms.IntegerField(min_value=1)
    tipoIncidencia = forms.ChoiceField(choices=GarantiaReclamo.Tipo.choices, error_messages={
        "invalid_choice": "Elige un tipo de falla de la lista."})
    descripcion = forms.CharField(min_length=10, max_length=2000, strip=True, error_messages={
        "min_length": "Describe el daño con un poco más de detalle (mínimo 10 caracteres).",
        "required": "Describe el daño para poder tramitar tu solicitud."})
