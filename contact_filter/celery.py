from celery import Celery
from celery.schedules import crontab
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'contact_filter.settings')

app = Celery('contact_filter')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'cleanup-expired-files': {
        'task': 'apps.processing.tasks_beat.cleanup_expired_files',
        'schedule': crontab(hour=3, minute=0),
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
