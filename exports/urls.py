from django.urls import path
from .views import ExportProfilesCSVView, ExportUsersCSVView

urlpatterns = [
    path('profiles/', ExportProfilesCSVView.as_view()),
    path('users/', ExportUsersCSVView.as_view()),
]