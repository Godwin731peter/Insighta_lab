from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("admin", "Admin"),
        ("analyst", "Analyst"),
    ]
    github_id = models.BigIntegerField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="analyst")
    avatar_url = models.URLField(blank=True)
    github_login = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.username} ({self.role})"