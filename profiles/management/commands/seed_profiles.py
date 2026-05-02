import json
import os
from django.core.management.base import BaseCommand
from task1.models import Profile

class Command(BaseCommand):
    help = "Seed database with 2026 profiles"

    def handle(self, *args, **kwargs):

         # Always find the JSON file relative to the project root
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        json_path = os.path.join(base_dir, "seed_profiles.json")

        if not os.path.exists(json_path):
            self.stdout.write(self.style.ERROR(f"❌ seed_profiles.json not found at {json_path}"))
            return


        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        profiles = data.get("profiles", [])

        created_count = 0
        updated_count = 0

        for item in profiles:
            obj, created = Profile.objects.update_or_create(
                name=item.get("name"),  # ✅ unique field
                defaults={
                    "gender": item.get("gender"),
                    "gender_probability": float(item.get("gender_probability", 0)),
                    "sample_size": 0,
                    "age": int(item.get("age", 0)),
                    "age_group": item.get("age_group"),
                    "country_id": item.get("country_id"),
                    "country_name": item.get("country_name", ""),
                    "country_probability": float(item.get("country_probability", 0)),
                }
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"✅ Done: {created_count} created, {updated_count} updated"
        ))