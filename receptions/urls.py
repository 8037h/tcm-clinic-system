from django.urls import path

from . import views

app_name = "receptions"

urlpatterns = [
    path("", views.reception_list, name="list"),
    path("export/", views.reception_export, name="export"),
    path("add/", views.reception_add, name="add"),
    path("<int:pk>/action/<str:action>/", views.reception_action, name="action"),
    path("<int:pk>/", views.reception_detail, name="detail"),
    path("<int:pk>/edit/", views.reception_edit, name="edit"),
    path("<int:pk>/delete/", views.reception_delete, name="delete"),
]
