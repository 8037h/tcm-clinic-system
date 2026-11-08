from django.contrib import admin

from .models import ReceptionRecord


@admin.register(ReceptionRecord)
class ReceptionRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "patient_name", "doctor", "department", "visit_time", "status", "updated_at")
    list_filter = ("status", "doctor__department", "visit_time")
    search_fields = ("patient_name", "doctor__name", "chief_complaint", "diagnosis")
    date_hierarchy = "visit_time"

    def delete_queryset(self, request, queryset):
        for record in queryset:
            record.delete()
