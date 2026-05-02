from django.shortcuts import render

# Create your views here.
import csv
from django.http import HttpResponse
from rest_framework.views import APIView
from core.permissions import IsAdmin
from profiles.models import Profile

class ExportCSVView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="profiles.csv"'

        writer = csv.writer(response)
        writer.writerow(['Name', 'Age', 'Gender'])

        for p in Profile.objects.all():
            writer.writerow([p.name, p.age, p.gender])

        return response