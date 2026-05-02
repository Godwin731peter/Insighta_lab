from rest_framework import serializers
from .models import Profile


class ProfileFullSerializer(serializers.ModelSerializer):
    """Used for POST, GET single profile — returns all fields."""
    id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(
        format='%Y-%m-%dT%H:%M:%SZ', read_only=True
    )

    class Meta:
        model = Profile
        fields = [
            'id',
            'name',
            'gender',
            'gender_probability',
            'sample_size',
            'age',
            'age_group',
            'country_id',
            'country_name',
            'country_probability',
            'created_at',
        ]


class ProfileListSerializer(serializers.ModelSerializer):
    """Used for GET all profiles — returns subset of fields."""
    id = serializers.UUIDField(read_only=True)
    created_at = serializers.DateTimeField(
        format='%Y-%m-%dT%H:%M:%SZ', read_only=True
    )


    class Meta:
        model = Profile
        fields = [
            'id',
            'name',
            'gender',
            'gender_probability',
            'age',
            'age_group',
            'country_id',
            'country_name',
            'country_probability',
            'created_at',
        ]


class ProfileCreateSerializer(serializers.Serializer):
    """Used to validate incoming POST request body."""
    name = serializers.CharField(max_length=255)

    def validate_name(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError('Name cannot be empty.')
        return value.strip().lower()