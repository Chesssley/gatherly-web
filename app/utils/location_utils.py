import json
import os
import re
import time
from datetime import datetime
from ipaddress import ip_address
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import urlopen

from flask import request


LOCAL_IPS = {"127.0.0.1", "::1", "localhost"}
UNKNOWN_LOCATION = {"city": None, "region": "未知地区"}
UNKNOWN_REGION_LABEL = "未知"
UNKNOWN_LOCATION_LABELS = {"未知", "未知地区"}
_MISSING = object()
IP_REGION_SPLIT_PATTERN = re.compile(r"\s*(?:/|／|,|，|、|\|)\s*")
COORDINATE_PATTERN = re.compile(r"^-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?$")
CLIENT_IP_HEADERS = (
    "CF-Connecting-IP",
    "X-Forwarded-For",
    "X-Real-IP",
)
CITY_HEADERS = (
    "X-Forwarded-City",
    "X-Appengine-City",
    "CF-IPCity",
    "CloudFront-Viewer-City",
    "X-Geo-City",
)
REGION_HEADERS = (
    "X-Forwarded-Region",
    "X-Appengine-Region",
    "CF-Region",
    "CloudFront-Viewer-Country-Region",
    "X-Geo-Region",
)
COUNTRY_HEADERS = (
    "X-Forwarded-Country",
    "X-Appengine-Country",
    "CF-IPCountry",
    "CloudFront-Viewer-Country",
    "X-Geo-Country",
)
COUNTRY_NAME_MAP = {
    "CN": "中国",
    "China": "中国",
    "People's Republic of China": "中国",
    "HK": "香港",
    "Hong Kong": "香港",
    "MO": "澳门",
    "Macao": "澳门",
    "Macau": "澳门",
    "TW": "台湾",
    "Taiwan": "台湾",
    "US": "美国",
    "USA": "美国",
    "United States": "美国",
    "United States of America": "美国",
    "CA": "加拿大",
    "Canada": "加拿大",
    "GB": "英国",
    "UK": "英国",
    "United Kingdom": "英国",
    "Great Britain": "英国",
    "JP": "日本",
    "Japan": "日本",
    "KR": "韩国",
    "South Korea": "韩国",
    "Korea, Republic of": "韩国",
    "SG": "新加坡",
    "Singapore": "新加坡",
    "AU": "澳大利亚",
    "Australia": "澳大利亚",
    "DE": "德国",
    "Germany": "德国",
    "FR": "法国",
    "France": "法国",
    "IT": "意大利",
    "Italy": "意大利",
    "ES": "西班牙",
    "Spain": "西班牙",
    "NL": "荷兰",
    "Netherlands": "荷兰",
    "IN": "印度",
    "India": "印度",
}
COUNTRY_CODE_NAMES = COUNTRY_NAME_MAP
CHINA_COUNTRY_LABELS = {"中国"}
COUNTRY_LEVEL_REGION_LABELS = {"香港", "澳门", "台湾"}
IP_GEO_LOOKUP_URL = os.environ.get("IP_GEO_LOOKUP_URL", "https://ipwho.is/{ip}?lang=zh-CN")
IP_GEO_LOOKUP_TIMEOUT_SECONDS = 1.5
IP_GEO_CACHE_TTL_SECONDS = 1800
_IP_GEO_CACHE = {}


def _clean_location_value(value, max_length=80):
    value = (value or "").strip()
    if not value or value.lower() in {"unknown", "null", "none"}:
        return None
    return value[:max_length]


def _country_name(value):
    value = _clean_location_value(value)
    if not value:
        return None
    return COUNTRY_NAME_MAP.get(value.upper()) or COUNTRY_NAME_MAP.get(value) or value


def _is_china_country(country_code=None, country=None):
    country_label = _country_name(country_code) or _country_name(country)
    return country_label in CHINA_COUNTRY_LABELS


def _display_region_label(city=None, region=None, country=None, country_code=None):
    country_label = _country_name(country_code) or _country_name(country)
    if country_label and (
        (country_code and not _is_china_country(country_code, country))
        or country_label in COUNTRY_LEVEL_REGION_LABELS
    ):
        return _single_region_label(country_label)
    return _single_region_label(city, region, country_label)


def get_client_ip():
    """
    Return the current request client's public-facing IP.
    In Render production, requests arrive through proxies that pass the client
    address in forwarded headers; prefer those trusted proxy headers here.
    Do not expose this raw IP in templates.
    """
    for header in CLIENT_IP_HEADERS:
        value = request.headers.get(header, "")
        if not value:
            continue
        if header == "X-Forwarded-For":
            for item in value.split(","):
                candidate = item.strip()
                if candidate:
                    return candidate
            continue
        candidate = value.strip()
        if candidate:
            return candidate

    return (request.remote_addr or "").strip() or None


def _is_private_or_local_ip(ip):
    if not ip or ip in LOCAL_IPS:
        return True
    try:
        parsed_ip = ip_address(ip)
    except ValueError:
        return True
    return (
        parsed_ip.is_private
        or parsed_ip.is_loopback
        or parsed_ip.is_link_local
        or parsed_ip.is_reserved
        or parsed_ip.is_multicast
    )


def _header_location():
    city = None
    region = None
    country = None
    country_code = None
    for header in CITY_HEADERS:
        city = _clean_location_value(request.headers.get(header))
        if city:
            break
    for header in REGION_HEADERS:
        region = _clean_location_value(request.headers.get(header))
        if region:
            break
    for header in COUNTRY_HEADERS:
        country_code = _clean_location_value(request.headers.get(header))
        country = _country_name(country_code)
        if country:
            break
    if city or region or country:
        return {"city": city, "region": region, "country": country, "country_code": country_code}
    return None


def _single_region_label(*values):
    for value in values:
        for clean_value in _region_parts(value):
            return clean_value
    return UNKNOWN_REGION_LABEL


def _ip_geo_lookup_enabled():
    value = os.environ.get("IP_GEO_LOOKUP_ENABLED")
    if value is None:
        return True
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _lookup_public_ip_location(ip):
    if not ip or not _ip_geo_lookup_enabled():
        return None

    cached = _IP_GEO_CACHE.get(ip)
    now = time.time()
    if cached and now - cached["time"] < IP_GEO_CACHE_TTL_SECONDS:
        return cached["location"]

    url = IP_GEO_LOOKUP_URL.format(ip=quote(ip, safe=""))
    try:
        with urlopen(url, timeout=IP_GEO_LOOKUP_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        _IP_GEO_CACHE[ip] = {"time": now, "location": None}
        return None

    if not isinstance(payload, dict) or payload.get("success") is False:
        _IP_GEO_CACHE[ip] = {"time": now, "location": None}
        return None

    location = {
        "city": _clean_location_value(payload.get("city")),
        "region": _clean_location_value(payload.get("region")),
        "country": _country_name(payload.get("country")),
        "country_code": _clean_location_value(payload.get("country_code")),
    }
    if not any(location.values()):
        location = None
    _IP_GEO_CACHE[ip] = {"time": now, "location": location}
    return location


def _stored_location_values(detected):
    label = format_ip_region(detected)
    if label == UNKNOWN_REGION_LABEL:
        return None, None
    city = detected.get("city") if isinstance(detected, dict) else None
    region = detected.get("region") if isinstance(detected, dict) else None
    country = detected.get("country") if isinstance(detected, dict) else None
    if city and locations_match(city, label):
        return city, region or country
    return None, label


def resolve_ip_region(ip):
    """
    Return one display-safe region label for the current request IP.
    Prefer trusted proxy/CDN geo headers from the same request, then fall back
    to a short-timeout public IP lookup for the current public exit IP.
    """
    header_location = _header_location()
    if header_location:
        return _display_region_label(
            header_location.get("city"),
            header_location.get("region"),
            header_location.get("country"),
            header_location.get("country_code"),
        )

    if _is_private_or_local_ip(ip):
        return UNKNOWN_REGION_LABEL

    public_location = _lookup_public_ip_location(ip)
    if public_location:
        return _display_region_label(
            public_location.get("city"),
            public_location.get("region"),
            public_location.get("country"),
            public_location.get("country_code"),
        )
    return UNKNOWN_REGION_LABEL


def detect_city_from_ip(ip):
    # Some deployment platforms or reverse proxies can provide coarse geo headers.
    # Without such headers, keep this dependency-free and fail closed.
    header_location = _header_location()
    if header_location:
        return header_location

    if _is_private_or_local_ip(ip):
        return UNKNOWN_LOCATION.copy()

    public_location = _lookup_public_ip_location(ip)
    if public_location:
        return public_location

    return UNKNOWN_LOCATION.copy()


def detect_current_request_location():
    return detect_city_from_ip(get_client_ip())


def update_user_detected_location(user, force=False):
    if not user:
        return None

    now = datetime.utcnow()
    client_ip = get_client_ip()
    detected = detect_city_from_ip(client_ip)
    user.last_location_detected_at = now
    if detected:
        detected_city, detected_region = _stored_location_values(detected)
        if user.detected_city != detected_city:
            user.detected_city = detected_city
        if user.detected_region != detected_region:
            user.detected_region = detected_region
    return detected


def _is_ip_address(value):
    try:
        ip_address(value)
    except ValueError:
        return False
    return True


def _usable_region_value(value):
    value = (value or "").strip()
    if (
        not value
        or value in UNKNOWN_LOCATION_LABELS
        or _is_ip_address(value)
        or COORDINATE_PATTERN.match(value)
    ):
        return None
    return value


def _region_parts(value):
    clean_value = _usable_region_value(value)
    if not clean_value:
        return []
    return [
        part
        for part in (
            _usable_region_value(part)
            for part in IP_REGION_SPLIT_PATTERN.split(clean_value)
        )
        if part
    ]


def format_ip_region(location_or_user=_MISSING):
    if location_or_user is _MISSING:
        return resolve_ip_region(get_client_ip())

    if not location_or_user:
        return UNKNOWN_REGION_LABEL

    if isinstance(location_or_user, dict):
        return _display_region_label(
            location_or_user.get("city"),
            location_or_user.get("region"),
            location_or_user.get("country"),
            location_or_user.get("country_code"),
        )
    else:
        return _single_region_label(
            getattr(location_or_user, "detected_city", None),
            _country_name(getattr(location_or_user, "detected_region", None))
            or getattr(location_or_user, "detected_region", None),
        )


def format_ip_region_label(location_or_user):
    return format_ip_region(location_or_user)


def location_values(location_or_user):
    label = format_ip_region(location_or_user)
    return [] if label == UNKNOWN_REGION_LABEL else [label]


def normalize_city(value):
    return (value or "").strip().casefold()


def locations_match(left, right):
    normalized_left = normalize_city(left)
    normalized_right = normalize_city(right)
    if not normalized_left or not normalized_right:
        return False
    return (
        normalized_left == normalized_right
        or normalized_left in normalized_right
        or normalized_right in normalized_left
    )
