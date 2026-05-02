from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('analyst', 'Analyst'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='analyst')
    github_id = models.CharField(max_length=255, unique=True, null=True, blank=True)