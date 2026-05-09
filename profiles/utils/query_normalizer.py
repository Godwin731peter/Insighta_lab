import hashlib
import json


NORMALIZED_GENDERS = {
    "woman": "female",
    "women": "female",
    "female": "female",

    "man": "male",
    "men": "male",
    "male": "male",
}


def normalize_filters(filters):

    normalized = {}

    if "gender" in filters:
        gender = filters["gender"].lower()
        normalized["gender"] = NORMALIZED_GENDERS.get(
            gender,
            gender
        )

    if "country_id" in filters:
        normalized["country_id"] = (
            filters["country_id"]
            .strip()
            .upper()
        )

    if "age_min" in filters:
        normalized["age_min"] = int(filters["age_min"])

    if "age_max" in filters:
        normalized["age_max"] = int(filters["age_max"])

    return normalized


def generate_cache_key(filters):

    normalized = normalize_filters(filters)

    canonical = json.dumps(
        normalized,
        sort_keys=True
    )

    return hashlib.sha256(
        canonical.encode()
    ).hexdigest()