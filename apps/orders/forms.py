from django import forms

from .models import GarantiaReclamo


class GarantiaForm(forms.Form):
    ventaId = forms.IntegerField(min_value=1, required=False)
    productoId = forms.IntegerField(min_value=1, required=False)
    tipoIncidencia = forms.ChoiceField(choices=GarantiaReclamo.Tipo.choices, error_messages={
        "invalid_choice": "Elige un tipo de falla de la lista."})
    descripcion = forms.CharField(min_length=10, max_length=2000, strip=True, error_messages={
        "min_length": "Describe el daño con un poco más de detalle (mínimo 10 caracteres).",
        "required": "Describe el daño para poder tramitar tu solicitud."})

    def clean(self):
        datos = super().clean()
        if datos.get("tipoIncidencia") == GarantiaReclamo.Tipo.QUEJA_GENERAL:
            return datos
        if not datos.get("ventaId"):
            self.add_error("ventaId", "Selecciona un pedido para tramitar esta solicitud.")
        if not datos.get("productoId"):
            self.add_error("productoId", "Selecciona la prenda relacionada con la solicitud.")
        return datos
