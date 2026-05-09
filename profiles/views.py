from django.shortcuts import render
import re
import requests
from django.http import JsonResponse
from django.core.cache import cache
from .utils.query_normalizer import generate_cache_key
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from accounts.authentication import CookieOrHeaderJWTAuthentication
from core.permissions import IsAnalyst
from .tasks import process_csv


# Create your views here.
from .models import Profile
from .serializers import (
    ProfileFullSerializer,
    ProfileListSerializer,
    ProfileCreateSerializer,
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

def cors_headers(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


def error_response(message, status_code):
    return Response(
        {'status': 'error', 'message': message},
        status=status_code
    )


def get_age_group(age):
    if age <= 12:
        return 'child'
    elif age <= 17:
        return 'teenager'
    elif age <= 64:
        return 'adult'
    else:
        return 'senior'


# ─── External API ─────────────────────────────────────────────────────────────

def fetch_external_apis(name):
    """
    Calls Genderize, Agify, and Nationalize APIs.
    Returns (data_dict, error_message) — one will be None.
    """
    # Genderize
    try:
        g_resp = requests.get(
            'https://api.genderize.io', params={'name': name}, timeout=5
        )
        g_resp.raise_for_status()
        g_data = g_resp.json()
    except Exception:
        return None, 'Genderize returned an invalid response'

    gender = g_data.get('gender')
    gender_probability = g_data.get('probability')
    sample_size = g_data.get('count')

    if gender is None or sample_size == 0:
        return None, 'Genderize returned an invalid response'

    # Agify
    try:
        a_resp = requests.get(
            'https://api.agify.io', params={'name': name}, timeout=5
        )
        a_resp.raise_for_status()
        a_data = a_resp.json()
    except Exception:
        return None, 'Agify returned an invalid response'

    age = a_data.get('age')
    if age is None:
        return None, 'Agify returned an invalid response'

    # Nationalize
    try:
        n_resp = requests.get(
            'https://api.nationalize.io', params={'name': name}, timeout=5
        )
        n_resp.raise_for_status()
        n_data = n_resp.json()
    except Exception:
        return None, 'Nationalize returned an invalid response'

    countries = n_data.get('country', [])
    if not countries:
        return None, 'Nationalize returned an invalid response'

    top_country = max(countries, key=lambda c: c.get('probability', 0))
    country_id = top_country.get('country_id')
    country_probability = top_country.get('probability')

    return {
        'gender': gender,
        'gender_probability': gender_probability,
        'sample_size': sample_size,
        'age': age,
        'age_group': get_age_group(age),
        'country_id': country_id,
        'country_name': '',          # Nationalize does not return full name
        'country_probability': country_probability,
    }, None


# ─── Filter & Sort helpers ────────────────────────────────────────────────────

VALID_SORT_FIELDS = {'age', 'created_at', 'gender_probability'}
VALID_ORDERS = {'asc', 'desc'}
VALID_AGE_GROUPS = {'child', 'teenager', 'adult', 'senior'}
VALID_GENDERS = {'male', 'female'}


def apply_filters(queryset, params):
    """
    Apply all supported filters from query params.
    Returns (filtered_queryset, error_response_or_None).
    """
    gender = params.get('gender')
    if gender is not None:
        if gender.lower() not in VALID_GENDERS:
            return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)
        queryset = queryset.filter(gender__iexact=gender)

    age_group = params.get('age_group')
    if age_group is not None:
        if age_group.lower() not in VALID_AGE_GROUPS:
            return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)
        queryset = queryset.filter(age_group__iexact=age_group)

    country_id = params.get('country_id')
    if country_id is not None:
        queryset = queryset.filter(country_id__iexact=country_id)

    min_age = params.get('min_age')
    if min_age is not None:
        try:
            queryset = queryset.filter(age__gte=int(min_age))
        except (ValueError, TypeError):
            return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    max_age = params.get('max_age')
    if max_age is not None:
        try:
            queryset = queryset.filter(age__lte=int(max_age))
        except (ValueError, TypeError):
            return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    min_gender_probability = params.get('min_gender_probability')
    if min_gender_probability is not None:
        try:
            val = float(min_gender_probability)
            if not (0.0 <= val <= 1.0):
                raise ValueError
            queryset = queryset.filter(gender_probability__gte=val)
        except (ValueError, TypeError):
            return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    min_country_probability = params.get('min_country_probability')
    if min_country_probability is not None:
        try:
            val = float(min_country_probability)
            if not (0.0 <= val <= 1.0):
                raise ValueError
            queryset = queryset.filter(country_probability__gte=val)
        except (ValueError, TypeError):
            return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    return queryset, None


def apply_sort(queryset, params):
    """
    Apply sort_by and order params.
    Returns (sorted_queryset, error_response_or_None).
    """
    sort_by = params.get('sort_by', 'created_at')
    order = params.get('order', 'asc').lower()

    if sort_by not in VALID_SORT_FIELDS:
        return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)
    if order not in VALID_ORDERS:
        return None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    field = sort_by if order == 'asc' else f'-{sort_by}'
    return queryset.order_by(field), None


def apply_pagination(queryset, params):
    """
    Apply page and limit params.
    Returns (page_data, page, limit, total, error_response_or_None).
    """
    try:
        page = int(params.get('page', 1))
        if page < 1:
            raise ValueError
    except (ValueError, TypeError):
        return None, None, None, None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    try:
        limit = int(params.get('limit', 10))
        if limit < 1:
            raise ValueError
        limit = min(limit, 50)
    except (ValueError, TypeError):
        return None, None, None, None, error_response('Invalid query parameters', status.HTTP_422_UNPROCESSABLE_ENTITY)

    total = queryset.count()
    offset = (page - 1) * limit
    page_data = queryset[offset: offset + limit]
    return page_data, page, limit, total, None


# ─── Natural Language Parser ──────────────────────────────────────────────────

COUNTRY_MAP = {
    # Africa
    'nigeria': 'NG', 'nigerian': 'NG',
    'ghana': 'GH', 'ghanaian': 'GH',
    'kenya': 'KE', 'kenyan': 'KE',
    'angola': 'AO', 'angolan': 'AO',
    'south africa': 'ZA', 'south african': 'ZA',
    'egypt': 'EG', 'egyptian': 'EG',
    'ethiopia': 'ET', 'ethiopian': 'ET',
    'senegal': 'SN', 'senegalese': 'SN',
    'cameroon': 'CM', 'cameroonian': 'CM',
    'ivory coast': 'CI', "cote d'ivoire": 'CI', 'ivorian': 'CI',
    'morocco': 'MA', 'moroccan': 'MA',
    'tanzania': 'TZ', 'tanzanian': 'TZ',
    'uganda': 'UG', 'ugandan': 'UG',
    'mozambique': 'MZ', 'mozambican': 'MZ',
    'madagascar': 'MG',
    'benin': 'BJ', 'beninese': 'BJ',
    'mali': 'ML', 'malian': 'ML',
    'burkina faso': 'BF',
    'niger': 'NE', 'nigerien': 'NE',
    'chad': 'TD', 'chadian': 'TD',
    'guinea': 'GN', 'guinean': 'GN',
    'zimbabwe': 'ZW', 'zimbabwean': 'ZW',
    'zambia': 'ZM', 'zambian': 'ZM',
    'rwanda': 'RW', 'rwandan': 'RW',
    'somalia': 'SO', 'somali': 'SO',
    'sudan': 'SD', 'sudanese': 'SD',
    'congo': 'CD', 'congolese': 'CD',
    'togo': 'TG', 'togolese': 'TG',
    'sierra leone': 'SL',
    'liberia': 'LR', 'liberian': 'LR',
    'eritrea': 'ER', 'eritrean': 'ER',
    'malawi': 'MW', 'malawian': 'MW',
    'namibia': 'NA', 'namibian': 'NA',
    'botswana': 'BW',
    'gabon': 'GA', 'gabonese': 'GA',
    'gambia': 'GM', 'gambian': 'GM',
    'algeria': 'DZ', 'algerian': 'DZ',
    'libya': 'LY', 'libyan': 'LY',
    'tunisia': 'TN', 'tunisian': 'TN',
    'mauritania': 'MR',
    'burundi': 'BI', 'burundian': 'BI',
    'south sudan': 'SS',
    'lesotho': 'LS',
    'eswatini': 'SZ',
    'mauritius': 'MU', 'mauritian': 'MU',
    'seychelles': 'SC',
    'comoros': 'KM',
    'djibouti': 'DJ',
    'cape verde': 'CV',
    'sao tome': 'ST',
    'equatorial guinea': 'GQ',
    'guinea-bissau': 'GW',
    # Global
    'us': 'US', 'usa': 'US', 'united states': 'US', 'american': 'US',
    'uk': 'GB', 'united kingdom': 'GB', 'british': 'GB',
    'france': 'FR', 'french': 'FR',
    'germany': 'DE', 'german': 'DE',
    'india': 'IN', 'indian': 'IN',
    'china': 'CN', 'chinese': 'CN',
    'brazil': 'BR', 'brazilian': 'BR',
    'canada': 'CA', 'canadian': 'CA',
    'australia': 'AU', 'australian': 'AU',
    'japan': 'JP', 'japanese': 'JP',
    'mexico': 'MX', 'mexican': 'MX',
    'italy': 'IT', 'italian': 'IT',
    'spain': 'ES', 'spanish': 'ES',
    'portugal': 'PT', 'portuguese': 'PT',
}


def parse_natural_language(q):
    """
    Parse a plain-English query string into a filter dict.
    Returns a dict of filter kwargs, or None if the query cannot be interpreted.

    Recognised patterns
    ---────────────────
    Gender  : male/males/man/men/boy  |  female/females/woman/women/girl
              "male and female" → no gender filter
    Age kw  : child/children | teenager/teen | adult | senior/elderly/old
    "young" : maps to min_age=16, max_age=24  (not a stored age_group)
    Numeric : above/over/older than X  |  below/under/younger than X
              between X and Y  |  aged X
    Country : 60+ country names / adjectives  |  "from <country>"
    """
    if not q or not q.strip():
        return None

    text = q.lower().strip()
    filters = {}
    interpreted = False

    # ── Gender ────────────────────────────────────────────────────────────────
    no_gender_phrases = ('male and female', 'female and male', 'both genders', 'all genders')
    if any(p in text for p in no_gender_phrases):
        interpreted = True          # explicitly asked for both — no gender filter
    elif re.search(r'\b(female|females|woman|women|girl|girls)\b', text):
        filters['gender'] = 'female'
        interpreted = True
    elif re.search(r'\b(male|males|man|men|boy|boys)\b', text):
        filters['gender'] = 'male'
        interpreted = True

    # ── Age-group keywords ────────────────────────────────────────────────────
    if re.search(r'\b(child|children|kids?)\b', text):
        filters['age_group'] = 'child'
        interpreted = True
    elif re.search(r'\b(teenagers?|teens?|adolescents?)\b', text):
        filters['age_group'] = 'teenager'
        interpreted = True
    elif re.search(r'\b(seniors?|elderly|old\s+people|old\s+person)\b', text):
        filters['age_group'] = 'senior'
        interpreted = True
    elif re.search(r'\b(adults?)\b', text):
        filters['age_group'] = 'adult'
        interpreted = True

    # ── "young" → ages 16–24 (parsing only, not a stored age_group) ──────────
    if re.search(r'\byoung\b', text):
        filters['min_age'] = 16
        filters['max_age'] = 24
        interpreted = True

    # ── Numeric age filters ───────────────────────────────────────────────────
    above = re.search(r'\b(?:above|over|older\s+than|greater\s+than|more\s+than)\s+(\d+)', text)
    if above:
        filters['min_age'] = int(above.group(1))
        interpreted = True

    below = re.search(r'\b(?:below|under|younger\s+than|less\s+than)\s+(\d+)', text)
    if below:
        filters['max_age'] = int(below.group(1))
        interpreted = True

    between = re.search(r'\bbetween\s+(\d+)\s+and\s+(\d+)', text)
    if between:
        filters['min_age'] = int(between.group(1))
        filters['max_age'] = int(between.group(2))
        interpreted = True

    aged = re.search(r'\baged?\s+(\d+)\b', text)
    if aged:
        filters['min_age'] = int(aged.group(1))
        filters['max_age'] = int(aged.group(1))
        interpreted = True

    # ── Country — longest match first to avoid 'niger' beating 'nigeria' ─────
    for country_name in sorted(COUNTRY_MAP.keys(), key=len, reverse=True):
        if re.search(r'\b' + re.escape(country_name) + r'\b', text):
            filters['country_id'] = COUNTRY_MAP[country_name]
            interpreted = True
            break

    if not interpreted:
        return None

    return filters


def nl_filters_to_queryset(filters, queryset):
    """Apply a parsed NL filter dict to a queryset."""
    if 'gender' in filters:
        queryset = queryset.filter(gender=filters['gender'])
    if 'age_group' in filters:
        queryset = queryset.filter(age_group=filters['age_group'])
    if 'country_id' in filters:
        queryset = queryset.filter(country_id=filters['country_id'])
    if 'min_age' in filters:
        queryset = queryset.filter(age__gte=filters['min_age'])
    if 'max_age' in filters:
        queryset = queryset.filter(age__lte=filters['max_age'])
    return queryset


# ─── Views ────────────────────────────────────────────────────────────────────

class HealthView(APIView):
    def get(self, request):
        response = Response({'status': 'ok'})
        return cors_headers(response)


class ProfileListView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAnalyst]

    def options(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_200_OK)
        return cors_headers(response)

    def get(self, request):
        """
        GET /api/profiles/

        Filters  : gender, age_group, country_id, min_age, max_age,
                   min_gender_probability, min_country_probability
        Sorting  : sort_by (age|created_at|gender_probability), order (asc|desc)
        Pagination: page (default 1), limit (default 10, max 50)
        """
        queryset = Profile.objects.all()

        # ── Filters ──
        queryset, err = apply_filters(queryset, request.query_params)
        if err:
            return cors_headers(err)

        # ── Sort ──
        queryset, err = apply_sort(queryset, request.query_params)
        if err:
            return cors_headers(err)

        # ── Paginate ──
        page_data, page, limit, total, err = apply_pagination(queryset, request.query_params)
        if err:
            return cors_headers(err)

        serializer = ProfileListSerializer(page_data, many=True)
        response = Response({
            'status': 'success',
            'page': page,
            'limit': limit,
            'total': total,
            'data': serializer.data,
        }, status=status.HTTP_200_OK)
        return cors_headers(response)

    def post(self, request):
        """POST /api/profiles/ — create a new profile via external APIs."""
        input_serializer = ProfileCreateSerializer(data=request.data)

        if not input_serializer.is_valid():
            response = error_response('Bad Request', status.HTTP_400_BAD_REQUEST)
            return cors_headers(response)

        name = input_serializer.validated_data['name']

        # Idempotency
        existing = Profile.objects.filter(name=name).first()
        if existing:
            serializer = ProfileFullSerializer(existing)
            response = Response({
                'status': 'success',
                'message': 'Profile already exists',
                'data': serializer.data,
            }, status=status.HTTP_200_OK)
            return cors_headers(response)

        # Fetch external APIs
        api_data, api_error = fetch_external_apis(name)
        if api_error:
            response = error_response(api_error, status.HTTP_502_BAD_GATEWAY)
            return cors_headers(response)

        profile = Profile.objects.create(name=name, **api_data)
        serializer = ProfileFullSerializer(profile)
        response = Response({
            'status': 'success',
            'data': serializer.data,
        }, status=status.HTTP_201_CREATED)
        return cors_headers(response)


class ProfileSearchView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAnalyst]

    def options(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_200_OK)
        return cors_headers(response)

    def get(self, request):
        """
        GET /api/profiles/search/?q=<natural language query>

        Converts a plain-English query into DB filters (rule-based, no LLMs).
        Supports the same pagination params as ProfileListView.

        Examples
        --------
        ?q=young males from nigeria
        ?q=females above 30
        ?q=adult males from kenya
        ?q=male and female teenagers above 17
        """
        q = request.query_params.get('q', '').strip()
        if not q:
            response = error_response('Missing or empty parameter', status.HTTP_400_BAD_REQUEST)
            return cors_headers(response)

        filters = parse_natural_language(q)
        if filters is None:
            response = Response(
                {'status': 'error', 'message': 'Unable to interpret query'},
                status=status.HTTP_400_BAD_REQUEST
            )
            return cors_headers(response)

        queryset = Profile.objects.all()
        queryset = nl_filters_to_queryset(filters, queryset)

        # Sort & paginate still apply
        queryset, err = apply_sort(queryset, request.query_params)
        if err:
            return cors_headers(err)

        page_data, page, limit, total, err = apply_pagination(queryset, request.query_params)
        if err:
            return cors_headers(err)

        serializer = ProfileListSerializer(page_data, many=True)
        response = Response({
            'status': 'success',
            'page': page,
            'limit': limit,
            'total': total,
            'data': serializer.data,
        }, status=status.HTTP_200_OK)
        return cors_headers(response)

        filters = {
            "gender": request.GET.get("gender"),
            "country_id": request.GET.get("country_id"),
            "age_min": request.GET.get("age_min"),
            "age_max": request.GET.get("age_max"),
        }

        cache_key = generate_cache_key(filters)

        cached_data = cache.get(cache_key)

        cache.set(cache_key, data, timeout=300)


        if cached_data:
            return Response(cached_data)


class ProfileDetailView(APIView):
    authentication_classes = [CookieOrHeaderJWTAuthentication]
    permission_classes = [IsAnalyst]

    def options(self, request, *args, **kwargs):
        response = Response(status=status.HTTP_200_OK)
        return cors_headers(response)

    def get_profile(self, profile_id):
        try:
            return Profile.objects.get(id=profile_id), None
        except (Profile.DoesNotExist, ValueError):
            return None, error_response('Profile not found', status.HTTP_404_NOT_FOUND)

    def get(self, request, profile_id):
        """GET /api/profiles/{id}/ — retrieve a single profile."""
        profile, err = self.get_profile(profile_id)
        if err:
            return cors_headers(err)

        serializer = ProfileFullSerializer(profile)
        response = Response({
            'status': 'success',
            'data': serializer.data,
        }, status=status.HTTP_200_OK)
        return cors_headers(response)

    def delete(self, request, profile_id):
        """DELETE /api/profiles/{id}/ — delete a profile."""
        profile, err = self.get_profile(profile_id)
        if err:
            return cors_headers(err)

        profile.delete()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        return cors_headers(response)

class CSVUploadView(APIView):

    def post(self, request):

        file = request.FILES.get("file")

        if not file:
            return Response(
                {"error": "No file uploaded"},
                status=400
            )

        file_path = f"uploads/{file.name}"

        with open(file_path, "wb+") as destination:

            for chunk in file.chunks():
                destination.write(chunk)

        process_csv.delay(file_path)

        return Response({
            "status": "processing"
        })