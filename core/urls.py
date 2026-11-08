from django.urls import path

from . import views


department_patterns = [
    path("", views.DepartmentListView.as_view(), name="list"),
    path("add/", views.DepartmentCreateView.as_view(), name="add"),
    path("<int:pk>/", views.DepartmentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.DepartmentUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.DepartmentDeleteView.as_view(), name="delete"),
]

doctor_patterns = [
    path("", views.DoctorListView.as_view(), name="list"),
    path("add/", views.DoctorCreateView.as_view(), name="add"),
    path("<int:pk>/", views.DoctorDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.DoctorUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.DoctorDeleteView.as_view(), name="delete"),
]

schedule_patterns = [
    path("", views.ScheduleListView.as_view(), name="list"),
    path("add/", views.ScheduleCreateView.as_view(), name="add"),
    path("<int:pk>/", views.ScheduleDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.ScheduleUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.ScheduleDeleteView.as_view(), name="delete"),
]

performance_patterns = [
    path("", views.PerformanceListView.as_view(), name="list"),
    path("export/", views.performance_export, name="export"),
    path("add/", views.PerformanceCreateView.as_view(), name="add"),
    path("<int:pk>/recalculate/", views.performance_recalculate, name="recalculate"),
    path("<int:pk>/action/<str:action>/", views.performance_action, name="action"),
    path("<int:pk>/", views.PerformanceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.PerformanceUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", views.PerformanceDeleteView.as_view(), name="delete"),
]
