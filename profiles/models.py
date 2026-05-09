from django.db import models
import uuid
from django.db.models import CheckConstraint

# Create your models here.

class Profile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)

    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]

    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    gender_probability = models.FloatField()
    sample_size = models.IntegerField()
    age = models.IntegerField()
    age_group = models.CharField(max_length=50)
    country_id = models.CharField(max_length=10)
    country_name = models.CharField(max_length=100, blank=True, default='')
    country_probability = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'profiles'

        constraints = [
            models.CheckConstraint(
                name='age_non_negative',
                check=models.Q(age__gte=0)
            )
        ]

        indexes = [
            models.Index(fields=['gender']),
            models.Index(fields=['age']),
            models.Index(fields=['country_id']),

            # Composite indexes for common queries
            models.Index(fields=['gender', 'age']),
            models.Index(fields=['country_id', 'age']),
            models.Index(fields=['country_id', 'gender']),

            # Sorting / recent queries
            models.Index(fields=['created_at']),
        ]
        

    def __str__(self):
        return self.name
