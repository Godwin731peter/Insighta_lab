import csv
from django.http import HttpResponse
from rest_framework.views import APIView
from core.permissions import IsAdmin
from profiles.models import Profile
from accounts.authentication import CookieOrHeaderJWTAuthentication


class ExportProfilesCSVView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAdmin]

    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="profiles.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'id', 'name', 'gender', 'gender_probability',
            'age', 'age_group', 'country_id', 'country_probability', 'created_at'
        ])

        for p in Profile.objects.all().order_by('id'):
            writer.writerow([
                p.id, p.name, p.gender, p.gender_probability,
                p.age, p.age_group, p.country_id, p.country_probability,
                p.created_at.isoformat() if hasattr(p, 'created_at') else '',
            ])

        return response


class ExportUsersCSVView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAdmin]

    def get(self, request):
        from accounts.models import User
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="users.csv"'

        writer = csv.writer(response)
        writer.writerow(['id', 'username', 'email', 'role', 'github_login', 'avatar_url'])

        for u in User.objects.all().order_by('id'):
            writer.writerow([
                u.id, u.username, u.email,
                u.role, u.github_login, u.avatar_url,
            ])

        return response