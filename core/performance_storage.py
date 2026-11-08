from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivatePerformanceStorage(FileSystemStorage):
    def __init__(self):
        # 旧附件保存在 BASE_DIR/performance，保留读取能力。
        super().__init__(location=settings.BASE_DIR, base_url=None)

    def url(self, name):
        raise ValueError("绩效附件只能通过授权视图访问。")


def performance_attachment_path(instance, filename):
    suffix = Path(filename).suffix.lower()[:12]
    return f"private_uploads/performance/{instance.pk or 'new'}/{uuid4().hex}{suffix}"
