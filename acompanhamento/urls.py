from django.urls import path

from . import views

app_name = "acompanhamento"

urlpatterns = [
    path("", views.inicio, name="inicio"),
]
