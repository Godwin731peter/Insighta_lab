from celery import Celery
import os

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE',
    'project_name.settings'
)

app = Celery('project_name')

app.config_from_object(
    'django.conf:settings',
    namespace='CELERY'
)

app.autodiscover_tasks()