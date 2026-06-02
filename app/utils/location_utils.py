from datetime import datetime, timedelta
from ipaddress import ip_address

from flask import request


LOCAL_IPS = {"127.0.0.1", "::1", "localhost"}
LOCAL_DEVELOPMENT_LOCATION = {"city": "本地开发环境", "region": "本地开发环境"}
UNKNOWN_LOCATION = {"city": None, "region": "未知地区"}
LOCATION_REFRESH_INTERVAL = timedelta(hours=12)
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
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        for item in forwarded_for.split(","):
            candidate = item.strip()
            if candidate:
                return candidate

    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip

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


def _is_local_development_ip(ip):
    if not ip:
        return False
    if ip in LOCAL_IPS:
        return True
    try:
        return ip_address(ip).is_loopback
    except ValueError:
        return False


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
        return {"city": city, "region": region or country}
    return None


def detect_city_from_ip(ip):
    # Some deployment platforms or reverse proxies can provide coarse geo headers.
    # Without such headers, keep this dependency-free and fail closed.
    header_location = _header_location()
    if header_location:
        return header_location

    if _is_local_development_ip(ip):
        return LOCAL_DEVELOPMENT_LOCATION.copy()

    if _is_private_or_local_ip(ip):
        return UNKNOWN_LOCATION.copy()

    return UNKNOWN_LOCATION.copy()


def update_user_detected_location(user, force=False):
    if not user:
        return None

    now = datetime.utcnow()
    client_ip = get_client_ip()
    if hasattr(user, "last_ip"):
        user.last_ip = client_ip
    if (
        not force
        and user.last_location_detected_at
        and now - user.last_location_detected_at < LOCATION_REFRESH_INTERVAL
    ):
        return {"city": user.detected_city, "region": user.detected_region}

    detected = detect_city_from_ip(client_ip)
    user.last_location_detected_at = now
    if detected:
        user.detected_city = detected.get("city")
        user.detected_region = detected.get("region")
    return detected


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
