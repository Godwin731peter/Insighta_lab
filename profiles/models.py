from django.db import models
from django.db import models
import uuid

# Create your models here.

class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    gender = models.CharField(max_length=50)
    gender_probability = models.FloatField()
    sample_size = models.IntegerField()
    age = models.IntegerField()
    age_group = models.CharField(max_length=50)
    country_id = models.CharField(max_length=10)
    country_name = models.CharField(max_length=255, blank=True, default='')
    country_probability = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'profiles'
        indexes = [
            models.Index(fields=['gender']),
            models.Index(fields=['age_group']),
            models.Index(fields=['country_id']),
            models.Index(fields=['age']),
            models.Index(fields=['created_at']),
            models.Index(fields=['gender_probability']),
            models.Index(fields=['country_probability']),
        ]

    def __str__(self):
        return self.name
