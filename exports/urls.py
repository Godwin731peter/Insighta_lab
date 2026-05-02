from django.urls import path
from .views import ExportCSVView

urlpatterns = [
    path('csv/', ExportCSVView.as_view(), name='export-csv'),
]