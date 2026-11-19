from django import forms


class CheckoutForm(forms.Form):
    destinatario = forms.CharField(label="Nombre de quien recibe", max_length=200)
    telefono = forms.CharField(label="Teléfono", max_length=30)
    direccion = forms.CharField(label="Dirección", max_length=255)
    apartamento = forms.CharField(label="Apartamento o complemento", max_length=120, required=False)
    ciudad = forms.CharField(label="Ciudad", max_length=100)
    departamento = forms.CharField(label="Departamento", max_length=60)
    codigo_postal = forms.CharField(label="Código postal", max_length=12, required=False)
