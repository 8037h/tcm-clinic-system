from django.db import migrations, models
import django.db.models.deletion


def link_existing_records(apps, schema_editor):
    ReceptionRecord = apps.get_model("receptions", "ReceptionRecord")
    Department = apps.get_model("core", "Department")
    Doctor = apps.get_model("core", "Doctor")
    for record in ReceptionRecord.objects.using(schema_editor.connection.alias).all():
        department_name = record.department.strip() or "未分类科室"
        doctor_name = record.doctor.strip() or "未指定医师"
        department, _ = Department.objects.using(schema_editor.connection.alias).get_or_create(name=department_name)
        doctor, _ = Doctor.objects.using(schema_editor.connection.alias).get_or_create(
            name=doctor_name, department_id=department.pk
        )
        record.doctor_ref_id = doctor.pk
        record.save(update_fields=["doctor_ref"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        ("receptions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="receptionrecord",
            name="patient_phone",
            field=models.CharField(blank=True, max_length=30, verbose_name="患者电话"),
        ),
        migrations.AddField(
            model_name="receptionrecord",
            name="schedule",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reception_records", to="core.schedule", verbose_name="对应排班"),
        ),
        migrations.AddField(
            model_name="receptionrecord",
            name="doctor_ref",
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name="reception_records", to="core.doctor", verbose_name="接诊医师"),
        ),
        migrations.RunPython(link_existing_records, migrations.RunPython.noop),
        migrations.RemoveField(model_name="receptionrecord", name="doctor"),
        migrations.RemoveField(model_name="receptionrecord", name="department"),
        migrations.RenameField(model_name="receptionrecord", old_name="doctor_ref", new_name="doctor"),
        migrations.AlterField(
            model_name="receptionrecord",
            name="doctor",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="reception_records", to="core.doctor", verbose_name="接诊医师"),
        ),
    ]
