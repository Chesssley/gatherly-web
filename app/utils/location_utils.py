import re
from datetime import datetime
from ipaddress import ip_address

from flask import request


LOCAL_IPS = {"127.0.0.1", "::1", "localhost"}
UNKNOWN_LOCATION = {"city": None, "region": "未知地区"}
UNKNOWN_REGION_LABEL = "未知"
UNKNOWN_LOCATION_LABELS = {"未知", "未知地区"}
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
COUNTRY_CODE_NAMES = {
    "CN": "中国",
    "HK": "中国香港",
    "MO": "中国澳门",
    "TW": "中国台湾",
    "US": "美国",
    "CA": "加拿大",
    "GB": "英国",
    "JP": "日本",
    "KR": "韩国",
    "SG": "新加坡",
    "AU": "澳大利亚",
    "DE": "德国",
    "FR": "法国",
    "IT": "意大利",
    "ES": "西班牙",
    "NL": "荷兰",
    "IN": "印度",
}


def _clean_location_value(value, max_length=80):
    value = (value or "").strip()
    if not value or value.lower() in {"unknown", "null", "none"}:
        return None
    return value[:max_length]


def _country_name(value):
    value = _clean_location_value(value)
    if not value:
        return None
    return COUNTRY_CODE_NAMES.get(value.upper(), value)


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
    for header in CITY_HEADERS:
        city = _clean_location_value(request.headers.get(header))
        if city:
            break
    for header in REGION_HEADERS:
        region = _clean_location_value(request.headers.get(header))
        if region:
            break
    for header in COUNTRY_HEADERS:
        country = _country_name(request.headers.get(header))
        if country:
            break
    if city or region or country:
        return {"city": city, "region": region, "country": country}
    return None


def detect_city_from_ip(ip):
    # Some deployment platforms or reverse proxies can provide coarse geo headers.
    # Without such headers, keep this dependency-free and fail closed.
    header_location = _header_location()
    if header_location:
        return header_location

    if _is_private_or_local_ip(ip):
        return UNKNOWN_LOCATION.copy()

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
        detected_city = detected.get("city")
        detected_region = detected.get("region") or detected.get("country")
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


def format_ip_region_label(location_or_user):
    if not location_or_user:
        return UNKNOWN_REGION_LABEL

    if isinstance(location_or_user, dict):
        values = (
            location_or_user.get("city"),
            location_or_user.get("region"),
            location_or_user.get("country"),
        )
    else:
        values = (
            getattr(location_or_user, "detected_city", None),
            getattr(location_or_user, "detected_region", None),
        )

    for value in values:
        for clean_value in _region_parts(value):
            return clean_value
    return UNKNOWN_REGION_LABEL


def location_values(location_or_user):
    label = format_ip_region_label(location_or_user)
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
