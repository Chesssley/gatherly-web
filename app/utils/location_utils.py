from datetime import datetime, timedelta
from ipaddress import ip_address

from flask import request


LOCAL_IPS = {"127.0.0.1", "::1", "localhost"}
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


def _clean_location_value(value, max_length=80):
    value = (value or "").strip()
    if not value or value.lower() in {"unknown", "null", "none"}:
        return None
    return value[:max_length]


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


def _header_location():
    city = None
    region = None
    for header in CITY_HEADERS:
        city = _clean_location_value(request.headers.get(header))
        if city:
            break
    for header in REGION_HEADERS:
        region = _clean_location_value(request.headers.get(header))
        if region:
            break
    if city or region:
        return {"city": city, "region": region}
    return None


def detect_city_from_ip(ip):
    if _is_private_or_local_ip(ip):
        return None

    # Some deployment platforms or reverse proxies can provide coarse geo headers.
    # Without such headers, keep this dependency-free and fail closed.
    return _header_location()


def update_user_detected_location(user, force=False):
    if not user:
        return None

    now = datetime.utcnow()
    if (
        not force
        and user.last_location_detected_at
        and now - user.last_location_detected_at < LOCATION_REFRESH_INTERVAL
    ):
        return {"city": user.detected_city, "region": user.detected_region}

    detected = detect_city_from_ip(get_client_ip())
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
