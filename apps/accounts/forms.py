from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()


class LoginForm(forms.Form):
    email = forms.EmailField(max_length=254)
    password = forms.CharField(strip=False, max_length=128)


class RegistroForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)
    password = forms.CharField(strip=False, max_length=128)

    def clean(self):
        datos = super().clean()
        if datos.get("password"):
            try:
                validate_password(datos["password"], User(name=datos.get("name", ""), email=datos.get("email", "")))
            except ValidationError as exc:
                self.add_error("password", exc)
        return datos


class CorreoForm(forms.Form):
    email = forms.EmailField(max_length=254)


class PerfilInfoForm(forms.Form):
    name = forms.CharField(max_length=150)
    email = forms.EmailField(max_length=254)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("Ese correo ya pertenece a otra cuenta.")
        return email


class PerfilClaveForm(forms.Form):
    current_password = forms.CharField(strip=False)
    new_password = forms.CharField(strip=False)
    new_password_confirmation = forms.CharField(strip=False)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_current_password(self):
        if not self.user.check_password(self.cleaned_data["current_password"]):
            raise ValidationError("La contraseña actual es incorrecta.")
        return self.cleaned_data["current_password"]

    def clean(self):
        datos = super().clean()
        nueva, confirmacion = datos.get("new_password"), datos.get("new_password_confirmation")
        if nueva and confirmacion and nueva != confirmacion:
            self.add_error("new_password_confirmation", "La nueva contraseña y su confirmación no coinciden.")
        elif nueva:
            try:
                validate_password(nueva, self.user)
            except ValidationError as exc:
                self.add_error("new_password", exc)
        return datos
