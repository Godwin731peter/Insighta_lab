from celery import shared_task
from .models import Profile

import csv


BATCH_SIZE = 5000


@shared_task
def process_csv(file_path):

    total_rows = 0
    inserted = 0
    skipped = 0

    reasons = {
        "missing_fields": 0,
        "invalid_age": 0,
        "invalid_gender": 0,
        "duplicate_name": 0,
        "malformed_row": 0,
    }

    batch = []

    try:

        with open(
            file_path,
            mode='r',
            encoding='utf-8'
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                total_rows += 1

                try:

                    # REQUIRED FIELDS
                    required_fields = [
                        "name",
                        "gender",
                        "age",
                        "age_group",
                        "country_id",
                    ]

                    if any(not row.get(field) for field in required_fields):

                        skipped += 1
                        reasons["missing_fields"] += 1
                        continue

                    # VALIDATE AGE
                    try:
                        age = int(row["age"])

                        if age < 0:
                            skipped += 1
                            reasons["invalid_age"] += 1
                            continue

                    except ValueError:

                        skipped += 1
                        reasons["invalid_age"] += 1
                        continue

                    # VALIDATE GENDER
                    gender = row["gender"].lower()

                    if gender not in ["male", "female"]:

                        skipped += 1
                        reasons["invalid_gender"] += 1
                        continue

                    # CREATE OBJECT
                    profile = Profile(
                        name=row["name"],
                        gender=gender,
                        gender_probability=float(
                            row.get(
                                "gender_probability",
                                0
                            )
                        ),
                        sample_size=int(
                            row.get(
                                "sample_size",
                                0
                            )
                        ),
                        age=age,
                        age_group=row["age_group"],
                        country_id=row["country_id"],
                        country_name=row.get(
                            "country_name",
                            ""
                        ),
                        country_probability=float(
                            row.get(
                                "country_probability",
                                0
                            )
                        ),
                    )

                    batch.append(profile)

                    # BULK INSERT
                    if len(batch) >= BATCH_SIZE:

                        created = Profile.objects.bulk_create(
                            batch,
                            batch_size=BATCH_SIZE,
                            ignore_conflicts=True
                        )

                        inserted += len(created)

                        batch.clear()

                except Exception:

                    skipped += 1
                    reasons["malformed_row"] += 1
                    continue

            # INSERT REMAINING ROWS
            if batch:

                created = Profile.objects.bulk_create(
                    batch,
                    batch_size=BATCH_SIZE,
                    ignore_conflicts=True
                )

                inserted += len(created)

    except UnicodeDecodeError:

        return {
            "status": "error",
            "message": "Invalid file encoding"
        }

    return {
        "status": "success",
        "total_rows": total_rows,
        "inserted": inserted,
        "skipped": skipped,
        "reasons": reasons
    }