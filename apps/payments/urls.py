from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.PaymentCreateView.as_view(), name="create"),
    path("webhook/", views.webhook, name="webhook"),
    path("<uuid:reference>/", views.PaymentDetailView.as_view(), name="detail"),
]
