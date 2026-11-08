from datetime import timedelta
from statistics import mean, pstdev, pvariance

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from receptions.models import ReceptionRecord

from .models import CrawledMedicalData, Department, Doctor, PerformanceRecord, Schedule


def analysis_snapshot():
    """All denominators include every reception status, including cancelled."""
    records = ReceptionRecord.objects.all()
    total = records.count()
    status_rows = [
        {"code": code, "name": label, "count": records.filter(status=code).count(),
         "probability": records.filter(status=code).count() / total if total else None}
        for code, label in ReceptionRecord.Status.choices
    ]
    department_rows = list(Department.objects.annotate(
        reception_count=Count("doctors__reception_records"),
        completed_count=Count("doctors__reception_records", filter=Q(doctors__reception_records__status=ReceptionRecord.Status.COMPLETED)),
    ).values("name", "reception_count", "completed_count").order_by("name"))
    for row in department_rows:
        count = row["reception_count"]
        row["probability"] = count / total if total else None
        row["completion_rate"] = row["completed_count"] / count if count else None

    daily_rows = list(records.annotate(day=TruncDate("visit_time")).values("day").annotate(count=Count("id")).order_by("day"))
    if daily_rows:
        start, end = daily_rows[0]["day"], daily_rows[-1]["day"]
        daily_map = {row["day"]: row["count"] for row in daily_rows}
        daily_counts = [daily_map.get(start + timedelta(days=n), 0) for n in range((end - start).days + 1)]
    else:
        start = end = None
        daily_counts = []

    today = timezone.localdate()
    last_seven = [today - timedelta(days=n) for n in range(6, -1, -1)]
    seven_day_counts = [records.filter(visit_time__date=day).count() for day in last_seven]
    doctor_rows = list(Doctor.objects.annotate(
        reception_count=Count("reception_records", distinct=True),
        schedule_count=Count("schedules", distinct=True),
    ).values("name", "reception_count", "schedule_count").order_by("-reception_count", "name"))
    performance_rows = list(Doctor.objects.annotate(
        score=Sum("performance_records__total_score")
    ).values("name", "score").order_by("-score", "name"))

    # Pearson r is meaningful only when both series have variation.
    correlation = None
    if len(doctor_rows) >= 2:
        xs = [row["schedule_count"] for row in doctor_rows]
        ys = [row["reception_count"] for row in doctor_rows]
        if pvariance(xs) and pvariance(ys):
            xm, ym = mean(xs), mean(ys)
            correlation = sum((x - xm) * (y - ym) for x, y in zip(xs, ys)) / (
                (sum((x - xm) ** 2 for x in xs) * sum((y - ym) ** 2 for y in ys)) ** 0.5
            )

    completed_count = records.filter(status=ReceptionRecord.Status.COMPLETED).count()
    cancelled_count = records.filter(status=ReceptionRecord.Status.CANCELLED).count()
    crawled_count = CrawledMedicalData.objects.count()
    crawled_categories = list(CrawledMedicalData.objects.values("category").annotate(count=Count("id")).order_by("-count", "category"))
    return {
        "total": total,
        "crawled_count": crawled_count,
        "crawled_categories": crawled_categories,
        "completed_count": completed_count,
        "completed_probability": completed_count / total if total else None,
        "cancelled_probability": cancelled_count / total if total else None,
        "status_rows": status_rows,
        "department_rows": department_rows,
        "daily_start": start,
        "daily_end": end,
        "daily_days": len(daily_counts),
        "daily_mean": mean(daily_counts) if daily_counts else None,
        "daily_variance": pvariance(daily_counts) if daily_counts else None,
        "daily_stddev": pstdev(daily_counts) if daily_counts else None,
        "correlation": correlation,
        "charts": {
            "dates": [day.isoformat() for day in last_seven],
            "seven_day_counts": seven_day_counts,
            "departments": [row["name"] for row in department_rows if row["reception_count"]],
            "department_counts": [row["reception_count"] for row in department_rows if row["reception_count"]],
            "statuses": [{"name": row["name"], "value": row["count"]} for row in status_rows] if total else [],
            "doctor_names": [row["name"] for row in doctor_rows if row["reception_count"]][:10],
            "doctor_counts": [row["reception_count"] for row in doctor_rows if row["reception_count"]][:10],
            "performance_names": [row["name"] for row in performance_rows if row["score"] is not None][:10],
            "performance_scores": [float(row["score"]) for row in performance_rows if row["score"] is not None][:10],
        },
    }


def dashboard_metrics():
    today = timezone.localdate()
    return {
        "doctors": Doctor.objects.count(),
        "departments": Department.objects.count(),
        "today_schedules": Schedule.objects.filter(schedule_date=today).count(),
        "today_receptions": ReceptionRecord.objects.filter(visit_time__date=today).count(),
        "month_receptions": ReceptionRecord.objects.filter(visit_time__year=today.year, visit_time__month=today.month).count(),
        "completed_receptions": ReceptionRecord.objects.filter(status=ReceptionRecord.Status.COMPLETED).count(),
        "pending_performances": PerformanceRecord.objects.filter(status=PerformanceRecord.Status.PENDING).count(),
        "crawled_count": CrawledMedicalData.objects.count(),
    }
