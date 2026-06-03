import unittest
from unittest.mock import patch

from flask import Flask

from app.utils.location_utils import (
    _IP_GEO_CACHE,
    format_ip_region,
    format_ip_region_label,
    get_client_ip,
    resolve_ip_region,
)


class LocationUtilsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        _IP_GEO_CACHE.clear()

    def test_get_client_ip_prefers_cf_connecting_ip(self):
        headers = {
            "CF-Connecting-IP": "203.0.113.10",
            "X-Forwarded-For": "198.51.100.20, 10.0.0.1",
            "X-Real-IP": "198.51.100.30",
        }
        with self.app.test_request_context("/", headers=headers):
            self.assertEqual(get_client_ip(), "203.0.113.10")

    def test_get_client_ip_uses_first_x_forwarded_for_value(self):
        with self.app.test_request_context(
            "/",
            headers={"X-Forwarded-For": "198.51.100.20, 10.0.0.1"},
        ):
            self.assertEqual(get_client_ip(), "198.51.100.20")

    def test_resolve_ip_region_prefers_city_over_country(self):
        with self.app.test_request_context(
            "/",
            headers={"CF-IPCity": "广州", "CF-IPCountry": "CN"},
        ):
            self.assertEqual(resolve_ip_region("203.0.113.10"), "广州")
            self.assertEqual(format_ip_region(), "广州")

    def test_resolve_ip_region_falls_back_to_country(self):
        with self.app.test_request_context(
            "/",
            headers={"CF-IPCountry": "US"},
        ):
            self.assertEqual(resolve_ip_region("203.0.113.10"), "美国")

    def test_resolve_ip_region_prefers_foreign_country_over_city(self):
        with self.app.test_request_context(
            "/",
            headers={"CF-IPCity": "Tokyo", "CF-IPCountry": "JP"},
        ):
            self.assertEqual(resolve_ip_region("203.0.113.10"), "日本")

    @patch("app.utils.location_utils._lookup_public_ip_location")
    def test_resolve_ip_region_uses_public_lookup_for_current_ip(self, lookup):
        lookup.return_value = {
            "city": "Mountain View",
            "region": "California",
            "country": "United States",
            "country_code": "US",
        }
        with self.app.test_request_context("/", environ_base={"REMOTE_ADDR": "8.8.8.8"}):
            self.assertEqual(resolve_ip_region("8.8.8.8"), "美国")
        lookup.assert_called_once_with("8.8.8.8")

    def test_resolve_ip_region_without_geo_headers_is_unknown(self):
        with self.app.test_request_context("/", environ_base={"REMOTE_ADDR": "127.0.0.1"}):
            self.assertEqual(resolve_ip_region("127.0.0.1"), "未知")

    def test_format_ip_region_returns_one_clean_region(self):
        self.assertEqual(
            format_ip_region_label({"city": "广州 / 中国", "country": "US"}),
            "广州",
        )

    def test_format_ip_region_filters_ip_address_values(self):
        self.assertEqual(format_ip_region_label({"city": "8.8.8.8"}), "未知")


if __name__ == "__main__":
    unittest.main()
