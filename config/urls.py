from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

urlpatterns = [
    # El admin nativo de Django vive aparte para no chocar con /admin/dashboard, /admin/ventas, etc.
    path("django-admin/", admin.site.urls),
    path("admin/", include("apps.dashboard.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.cart.urls")),
    path("", include("apps.orders.urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("", include("apps.accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
