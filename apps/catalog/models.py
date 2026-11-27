from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.db.models import Count, F, Sum
from django.db.models.functions import Coalesce
from django.utils.text import slugify

from apps.core.utils import imagen_url, sin_acentos

HEX_VALIDATOR = RegexValidator(r"^#[0-9a-fA-F]{6}$", "Usa un color en formato #RRGGBB.")


class Categoria(models.Model):
    """Una colección. Las tres base (Essentials, Octane, Waves) tienen página propia y no se borran."""

    BASE_SLUGS = ("essentials", "octane", "waves")

    nombre = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=110, unique=True, editable=False)
    descripcion = models.CharField(max_length=255, blank=True, default="")
    estado = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def clean(self):
        existe = Categoria.objects.filter(nombre__iexact=(self.nombre or "").strip()).exclude(pk=self.pk)
        if existe.exists():
            raise ValidationError({"nombre": "Ya existe una categoría con ese nombre."})

    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").strip()
        if not self.slug:  # el slug se fija al crear y no cambia si luego renombras la categoría
            base = slugify(self.nombre) or "categoria"
            slug, n = base, 2
            while Categoria.objects.filter(slug=slug).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    @property
    def es_base(self) -> bool:
        return self.slug in self.BASE_SLUGS

    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    class Insumo(models.TextChoices):
        TELAS = "Telas & Tejidos", "Telas & Tejidos (Algodón Pima, Fleece, Rib)"
        CONFECCION = "Confección Textil", "Taller de Confección & Ensamble"
        ESTAMPADO = "Estampado & Lavandería", "Estampado / Serigrafía / Tintorería"
        AVIOS = "Avíos & Marquillas", "Avíos, Cierres, Cordones & Marquillas"

    nombre = models.CharField("razón social", max_length=255)
    nit = models.CharField(max_length=30, unique=True, null=True, blank=True)
    contacto_nombre = models.CharField(max_length=120, blank=True, default="")
    telefono = models.CharField(max_length=40)
    correo = models.EmailField()
    direccion = models.CharField(max_length=255, blank=True, default="")
    ciudad = models.CharField(max_length=100)
    tipo_insumo = models.CharField(max_length=40, choices=Insumo.choices, default=Insumo.TELAS)
    calificacion_calidad = models.PositiveSmallIntegerField(
        default=5, validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    estado = models.BooleanField("activo", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "proveedor"
        verbose_name_plural = "proveedores"

    def save(self, *args, **kwargs):
        self.nit = (self.nit or "").strip() or None  # varios proveedores sin NIT no chocan entre sí
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class ProductoQuerySet(models.QuerySet):
    def activos(self):
        return self.filter(estado=Producto.Estado.ACTIVO)

    def con_stock_total(self):
        """Anota `stock_total_db` = stock del color Original + stock de cada variante."""
        return self.annotate(
            stock_total_db=F("stock_actual") + Coalesce(Sum("variantes__stock_actual"), 0)
        )

    def stock_bajo(self):
        """Con stock, pero en el mínimo o por debajo."""
        return self.con_stock_total().filter(stock_total_db__gt=0, stock_total_db__lte=F("stock_minimo"))

    def sin_stock(self):
        return self.con_stock_total().filter(stock_total_db__lte=0)


class Producto(models.Model):
    class Estado(models.TextChoices):
        ACTIVO = "activo", "Activo"
        INACTIVO = "inactivo", "Inactivo"

    class TipoTalla(models.TextChoices):
        AUTO = "auto", "Automático (según el nombre)"
        SUPERIOR = "superior", "Superior: S, M, L, XL"
        PANTALON = "pantalon", "Pantalón: 28 a 36"
        UNICA = "unica", "Talla única (sin selector)"

    TALLAS = {
        "superior": ["S", "M", "L", "XL"],
        "pantalon": ["28", "30", "32", "34", "36"],
        "unica": [],
    }
    PALABRAS_PANTALON = ("pantalon", "pantalo", "jean", "short")

    nombre = models.CharField(max_length=255)
    descripcion = models.CharField(max_length=255, blank=True, default="")
    precio = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(1)])
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.ACTIVO)
    imagen = models.CharField("imagen principal", max_length=500, blank=True, default="")
    modelo_3d = models.CharField("modelo 3D (GLB)", max_length=500, blank=True, default="")
    # Stock del color "Original". Cada variante de color tiene el suyo.
    stock_actual = models.PositiveIntegerField(default=0)
    stock_minimo = models.PositiveIntegerField(default=5)
    stock_maximo = models.PositiveIntegerField(default=100)
    tipo_talla = models.CharField(max_length=10, choices=TipoTalla.choices, default=TipoTalla.AUTO)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="productos")
    proveedor = models.ForeignKey(Proveedor, on_delete=models.PROTECT, related_name="productos")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductoQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        verbose_name = "producto"
        verbose_name_plural = "productos"

    def clean(self):
        if self.stock_maximo is not None and self.stock_minimo is not None \
                and self.stock_maximo < self.stock_minimo:
            raise ValidationError({"stock_maximo": "El stock máximo no puede ser menor que el mínimo."})

    # --- Imagen ---------------------------------------------------------------
    @property
    def imagen_url(self) -> str:
        return imagen_url(self.imagen)

    # --- Stock ----------------------------------------------------------------
    @property
    def stock_total(self) -> int:
        if hasattr(self, "stock_total_db"):
            return int(self.stock_total_db)
        return self.stock_actual + sum(v.stock_actual for v in self.variantes.all())

    @property
    def agotado(self) -> bool:
        return self.stock_total <= 0

    @property
    def estado_stock(self) -> str:
        total = self.stock_total
        if total <= 0:
            return "agotado"
        return "bajo" if total <= self.stock_minimo else "disponible"

    @property
    def activo(self) -> bool:
        return self.estado == self.Estado.ACTIVO

    # --- Tallas ---------------------------------------------------------------
    @property
    def tipo_talla_efectivo(self) -> str:
        if self.tipo_talla != self.TipoTalla.AUTO:
            return self.tipo_talla
        texto = sin_acentos(f"{self.nombre} {self.categoria.nombre if self.categoria_id else ''}")
        es_pantalon = any(p in texto for p in self.PALABRAS_PANTALON) or "bottom" in texto
        return "pantalon" if es_pantalon else "superior"

    @property
    def tallas(self) -> list:
        return self.TALLAS[self.tipo_talla_efectivo]

    @property
    def requiere_talla(self) -> bool:
        return bool(self.tallas)

    def __str__(self):
        return self.nombre


class ProductoImagen(models.Model):
    """Galería adicional. Se gestiona desde /django-admin/ (la tienda hoy no la muestra)."""

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="imagenes")
    imagen = models.CharField(max_length=500)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["orden", "id"]
        verbose_name = "imagen de galería"
        verbose_name_plural = "imágenes de galería"

    @property
    def imagen_url(self) -> str:
        return imagen_url(self.imagen)

    def __str__(self):
        return f"{self.producto} · {self.orden}"


class ProductoVariante(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="variantes")
    color = models.CharField(max_length=60)
    hex = models.CharField("muestra", max_length=7, default="#000000", validators=[HEX_VALIDATOR])
    imagen = models.CharField(max_length=500, blank=True, default="")
    stock_actual = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]
        verbose_name = "variante de color"
        verbose_name_plural = "variantes de color"
        constraints = [
            models.UniqueConstraint(fields=["producto", "color"], name="variante_color_unico_por_producto"),
        ]

    def clean(self):
        existe = ProductoVariante.objects.filter(
            producto_id=self.producto_id, color__iexact=(self.color or "").strip()
        ).exclude(pk=self.pk)
        if self.producto_id and existe.exists():
            raise ValidationError({"color": "Ese producto ya tiene una variante con ese color."})

    def save(self, *args, **kwargs):
        self.color = (self.color or "").strip()
        super().save(*args, **kwargs)

    @property
    def imagen_url(self) -> str:
        return imagen_url(self.imagen) if self.imagen else ""

    def __str__(self):
        return f"{self.producto} · {self.color}"
