from django.contrib import admin

from .models import CrawledMedicalData, Department, Doctor, OperationLog, PerformanceRecord, Schedule


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "updated_at")
    search_fields = ("name", "description")
    list_filter = ("status",)


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("name", "department", "title", "status", "user")
    search_fields = ("name", "phone", "department__name")
    list_filter = ("status", "department")


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("doctor", "department", "schedule_date", "start_time", "end_time", "status")
    search_fields = ("doctor__name", "doctor__department__name", "location")
    list_filter = ("status", "schedule_date", "doctor__department")
    readonly_fields = ("booked_patients",)


@admin.register(PerformanceRecord)
class PerformanceRecordAdmin(admin.ModelAdmin):
    list_display = ("doctor", "period_start", "period_end", "total_score", "status")
    search_fields = ("doctor__name", "abnormal_remark")
    list_filter = ("status", "period_start")
    readonly_fields = ("reception_count", "completed_count", "total_score", "status", "reviewer", "review_time")


@admin.register(OperationLog)
class OperationLogAdmin(admin.ModelAdmin):
    list_display = ("user", "module", "operation_type", "object_name", "created_at")
    search_fields = ("user__username", "module", "object_name", "description")
    list_filter = ("module", "operation_type", "created_at")
    readonly_fields = ("user", "module", "operation_type", "object_name", "description", "ip_address", "created_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CrawledMedicalData)
class CrawledMedicalDataAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "source_name", "publish_date", "crawled_at")
    search_fields = ("title", "category", "source_name", "raw_text")
    list_filter = ("category", "source_name", "crawled_at")
    readonly_fields = ("crawled_at",)
