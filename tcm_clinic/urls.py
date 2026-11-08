from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views

from core import views as core_views
from core import urls as core_urls
from core import performance_views

performance_patterns = [
    path("", performance_views.PerformanceListView.as_view(), name="list"),
    path("export/", performance_views.export, name="export"),
    path("add/", performance_views.PerformanceCreateView.as_view(), name="add"),
    path("<int:pk>/recalculate/", performance_views.recalculate, name="recalculate"),
    path("<int:pk>/action/<str:action>/", performance_views.action, name="action"),
    path("<int:pk>/attachment/", performance_views.attachment, name="attachment"),
    path("<int:pk>/", performance_views.PerformanceDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", performance_views.PerformanceUpdateView.as_view(), name="edit"),
    path("<int:pk>/delete/", performance_views.PerformanceDeleteView.as_view(), name="delete"),
]

urlpatterns = [
    path("", core_views.dashboard, name="dashboard"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("register/", core_views.register, name="register"),
    path("analysis/", core_views.analysis, name="analysis"),
    path("analysis/export/", core_views.analysis_export, name="analysis_export"),
    path("crawled-data/", core_views.crawled_data_list, name="crawled_data_list"),
    path("operation-logs/", core_views.operation_log_list, name="operation_log_list"),
    path("admin/", admin.site.urls),
    path("departments/", include((core_urls.department_patterns, "departments"), namespace="departments")),
    path("doctors/", include((core_urls.doctor_patterns, "doctors"), namespace="doctors")),
    path("schedules/", include((core_urls.schedule_patterns, "schedules"), namespace="schedules")),
    path("receptions/", include("receptions.urls")),
    path("performances/", include((performance_patterns, "performances"), namespace="performances")),
]
