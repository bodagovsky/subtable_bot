"""Shared Yandex Weather client for Alfred's MCP and scheduled report."""
from __future__ import annotations

import os
from typing import Any

import requests


YANDEX_WEATHER_URL = "https://api.weather.yandex.ru/v2/forecast"
# City-centre coordinates from GeoNames. Keeping them here avoids geocoding on
# every scheduled report.
YEREVAN_LATITUDE = 40.17765
YEREVAN_LONGITUDE = 44.51260


def _api_key() -> str:
    key = os.getenv("YANDEX_WEATHER_API_KEY", "").strip()
    if not key:
        raise RuntimeError("YANDEX_WEATHER_API_KEY is not configured")
    return key


def fetch_forecast(latitude: float, longitude: float) -> dict[str, Any]:
    """Fetch a Yandex Weather forecast without exposing the API key."""
    if not -90 <= latitude <= 90:
        raise ValueError("latitude must be between -90 and 90")
    if not -180 <= longitude <= 180:
        raise ValueError("longitude must be between -180 and 180")
    response = requests.get(
        YANDEX_WEATHER_URL,
        params={"lat": latitude, "lon": longitude},
        headers={"X-Yandex-Weather-Key": _api_key()},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()
