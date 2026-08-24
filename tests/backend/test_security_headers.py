"""Regressoes G33: politicas defensivas em respostas HTTP e launcher seguro."""
from __future__ import annotations

import requests

from main_app import startup_error_html


EXPECTED_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), geolocation=(), microphone=()",
}


def assert_security_headers(response):
    for name, value in EXPECTED_HEADERS.items():
        assert response.headers.get(name) == value

    csp = response.headers.get("Content-Security-Policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp
    assert "https://" not in csp


def test_security_headers_cover_static_success_and_error(live_server):
    successful_response = requests.get(f"{live_server}/", timeout=5)
    missing_response = requests.get(f"{live_server}/backend.py", timeout=5)

    assert successful_response.status_code == 200
    assert missing_response.status_code == 404
    assert_security_headers(successful_response)
    assert_security_headers(missing_response)


def test_security_headers_cover_api_json_error(live_server):
    response = requests.post(
        f"{live_server}/api/analyze",
        data=b"ignored-before-read",
        headers={"Origin": "https://evil.example.com"},
        timeout=5,
    )

    assert response.status_code == 403
    assert_security_headers(response)


def test_startup_traceback_is_html_escaped():
    rendered = startup_error_html("RuntimeError: <img src=x onerror=alert(1)>")

    assert "<img" not in rendered
    assert "&lt;img src=x onerror=alert(1)&gt;" in rendered
    assert rendered.startswith("<pre") and rendered.endswith("</pre>")
