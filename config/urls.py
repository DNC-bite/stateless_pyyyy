from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # El admin nativo de Django vive aparte para no chocar con /admin/dashboard, /admin/ventas, etc.
    path("django-admin/", admin.site.urls),
    path("", include("apps.cart.urls")),
    path("", include("apps.orders.urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("", include("apps.core.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.catalog.urls")),
]
