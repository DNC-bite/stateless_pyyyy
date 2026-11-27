from django import forms
from django.core.files.storage import default_storage
from django.core.validators import FileExtensionValidator
from django.forms import inlineformset_factory

from apps.accounts.models import Role, User
from apps.catalog.models import Categoria, Producto, ProductoImagen, ProductoVariante, Proveedor
from apps.orders.models import Envio, GarantiaReclamo, Venta

MAX_TAMANO_MODELO_3D = 150 * 1024 * 1024


class AdminModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            css_class = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                css_class = "form-select"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css_class}".strip()


class CategoriaForm(AdminModelForm):
    class Meta:
        model = Categoria
        fields = ("nombre", "descripcion", "estado")


class ProveedorForm(AdminModelForm):
    class Meta:
        model = Proveedor
        fields = (
            "nombre", "nit", "contacto_nombre", "telefono", "correo", "direccion",
            "ciudad", "tipo_insumo", "calificacion_calidad", "estado",
        )


class ImagenUploadForm(AdminModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._imagen_required = self.fields["imagen"].required
        self.fields["imagen"].widget = forms.HiddenInput()
        self.fields["imagen"].required = False
        self.fields["imagen_archivo"] = forms.ImageField(
            required=False,
            label="Imagen",
            widget=forms.FileInput(attrs={"accept": "image/*", "class": "image-upload-input"}),
        )

    def clean(self):
        cleaned_data = super().clean()
        if (
            self._imagen_required
            and not cleaned_data.get("imagen")
            and not cleaned_data.get("imagen_archivo")
        ):
            self.add_error("imagen_archivo", "Selecciona una imagen.")
        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        archivo = self.cleaned_data.get("imagen_archivo")
        if archivo:
            ruta = default_storage.save(f"productos/{archivo.name}", archivo)
            instance.imagen = default_storage.url(ruta)
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProductoForm(ImagenUploadForm):
    class Meta:
        model = Producto
        fields = (
            "nombre", "descripcion", "precio", "estado", "imagen", "modelo_3d", "stock_actual",
            "stock_minimo", "stock_maximo", "tipo_talla", "categoria", "proveedor",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["modelo_3d"].widget = forms.HiddenInput()
        self.fields["modelo_3d"].disabled = True
        self.fields["modelo_3d_archivo"] = forms.FileField(
            required=False,
            label="Modelo 3D (.glb)",
            validators=[FileExtensionValidator(["glb"])],
            widget=forms.FileInput(attrs={"accept": ".glb", "class": "form-control"}),
        )
        self.fields["modelo_3d_eliminar"] = forms.BooleanField(
            required=False,
            label="Quitar modelo 3D",
            widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        )

    def clean_modelo_3d_archivo(self):
        archivo = self.cleaned_data.get("modelo_3d_archivo")
        if archivo and archivo.size > MAX_TAMANO_MODELO_3D:
            raise forms.ValidationError("El modelo 3D no puede superar 150 MB.")
        return archivo

    def save(self, commit=True):
        instance = super().save(commit=False)
        archivo = self.cleaned_data.get("modelo_3d_archivo")
        if archivo:
            ruta = default_storage.save(f"productos/modelos_3d/{archivo.name}", archivo)
            instance.modelo_3d = default_storage.url(ruta)
        elif self.cleaned_data.get("modelo_3d_eliminar"):
            instance.modelo_3d = ""
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class ProductoVarianteForm(ImagenUploadForm):
    class Meta:
        model = ProductoVariante
        fields = ("color", "hex", "imagen", "stock_actual")


class ProductoImagenForm(ImagenUploadForm):
    class Meta:
        model = ProductoImagen
        fields = ("imagen", "orden")


ProductoVarianteFormSet = inlineformset_factory(
    Producto, ProductoVariante, form=ProductoVarianteForm, extra=1, can_delete=True
)
ProductoImagenFormSet = inlineformset_factory(
    Producto, ProductoImagen, form=ProductoImagenForm, extra=1, can_delete=True
)


class UsuarioForm(AdminModelForm):
    class Meta:
        model = User
        fields = ("name", "email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].queryset = Role.objects.filter(name__in=Role.BASE).order_by("id")


class VentaEstadoForm(forms.Form):
    estado = forms.ChoiceField(
        choices=[choice for choice in Venta.Estado.choices if choice[0] != Venta.Estado.CANCELADO],
        widget=forms.Select(attrs={"class": "form-select"}),
    )


class EnvioAdminForm(forms.Form):
    estado = forms.ChoiceField(
        choices=[choice for choice in Envio.Estado.choices if choice[0] != Envio.Estado.CANCELADO],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    transportadora = forms.ChoiceField(
        choices=[("", "Selecciona una transportadora"), *Envio.Transportadora.choices],
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    numero_guia = forms.CharField(
        max_length=60,
        required=False,
        label="Número de guía",
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )


class ReclamoAdminForm(AdminModelForm):
    respuesta_admin = forms.CharField(
        required=False,
        max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )

    class Meta:
        model = GarantiaReclamo
        fields = ("estado", "respuesta_admin")
        widgets = {
            "estado": forms.Select(attrs={"class": "form-select"}),
        }


class ReporteFiltroForm(forms.Form):
    desde = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    hasta = forms.DateField(
        required=False,
        input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        desde, hasta = cleaned_data.get("desde"), cleaned_data.get("hasta")
        if desde and hasta and desde > hasta:
            self.add_error("hasta", "La fecha final debe ser igual o posterior a la inicial.")
        return cleaned_data
