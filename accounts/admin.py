from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

# Register your models here.
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'github_login', 'github_id', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('username', 'email', 'github_login')
    ordering = ('username',)

    fieldsets = UserAdmin.fieldsets + (
        ('GitHub Info', {
            'fields': ('github_id', 'github_login', 'avatar_url', 'role')
        }),
    )