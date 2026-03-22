import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dateutil import parser

# Charles River at Waltham (01104500) publishes discharge (00060) but not water temp (00010) in NWIS IV.
# Fresh Pond gate house (Cambridge) is an active nearby surface-water proxy on the Charles basin.
_DEFAULT_USGS_TEMP_SITE = "422302071083801"


class ExternalDataClient:
    WEATHER_POINTS_URL = "https://api.weather.gov/points/42.37,-71.06"
    USGS_FLOW_URL = (
        "https://waterservices.usgs.gov/nwis/iv/?sites=01104500&parameterCd=00060&format=json"
    )

    def __init__(self, timeout_seconds: float = 12.0):
        self.timeout_seconds = timeout_seconds
        self._usgs_temp_site = os.environ.get(
            "USGS_WATER_TEMP_SITE", _DEFAULT_USGS_TEMP_SITE
        ).strip()

    async def fetch_hourly_conditions(self, date_str: str) -> list[dict[str, Any]]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            forecast_url = await self._get_hourly_forecast_url(client)
            forecast = await self._get_weather_forecast(client, forecast_url)
            flow = await self._get_usgs_series(client, self.USGS_FLOW_URL)
            temp_url = (
                "https://waterservices.usgs.gov/nwis/iv/"
                f"?sites={self._usgs_temp_site}&parameterCd=00010&format=json"
            )
            temp = await self._get_usgs_series(client, temp_url)

        # USGS has no future flow: use the latest observed cfs for every forecast
        # hour so the UI and physics see one consistent value (no per-hour mismatch
        # from ISO key timezone differences vs weather.gov).
        latest_flow_cfs = self._latest_series_value(flow)

        rows = []
        for period in forecast:
            ts = parser.isoparse(period["startTime"])
            if ts.date().isoformat() != date_str:
                continue

            speed_mph = self._parse_wind_speed_mph(period.get("windSpeed", "0 mph"))
            wind_compass = (period.get("windDirection") or "N").strip()
            wind_deg = self._wind_direction_to_degrees(wind_compass)
            hour_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()

            gust_raw = period.get("windGust")
            if gust_raw is None or gust_raw == "":
                wind_gust_mph = None
            else:
                wind_gust_mph = round(self._parse_wind_speed_mph(str(gust_raw)), 2)

            # USGS water temp (parameterCd 00010) is degrees Celsius; physics uses °F.
            # Hour keys rarely match NWS exactly (timezone), so pick nearest observation
            # in time to this forecast hour, else latest gauge reading.
            water_temp_f = self._water_temp_fahrenheit_for_hour(temp, ts)

            rows.append(
                {
                    "timestamp": hour_key,
                    "wind_speed": round(speed_mph, 2),
                    "wind_dir": round(wind_deg, 2),
                    "wind_compass": wind_compass.upper(),
                    "wind_gust_mph": wind_gust_mph,
                    "flow_rate": round(latest_flow_cfs, 2),
                    "water_temp": water_temp_f,
                }
            )
        return rows

    async def _get_hourly_forecast_url(self, client: httpx.AsyncClient) -> str:
        response = await client.get(self.WEATHER_POINTS_URL)
        response.raise_for_status()
        data = response.json()
        return data["properties"]["forecastHourly"]

    async def _get_weather_forecast(
        self, client: httpx.AsyncClient, forecast_url: str
    ) -> list[dict[str, Any]]:
        response = await client.get(
            forecast_url, headers={"User-Agent": "charles-river-split-predictor"}
        )
        response.raise_for_status()
        return response.json()["properties"]["periods"]

    async def _get_usgs_series(
        self, client: httpx.AsyncClient, url: str
    ) -> dict[str, float]:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()
        series = payload.get("value", {}).get("timeSeries", [])
        if not series:
            return {}
        value_sets = series[0].get("values", [])
        if not value_sets:
            return {}
        values = value_sets[0].get("value", [])
        normalized = {}
        for row in values:
            if "dateTime" not in row or "value" not in row:
                continue
            ts = parser.isoparse(row["dateTime"])
            hour_key = ts.replace(minute=0, second=0, microsecond=0).isoformat()
            normalized[hour_key] = float(row["value"])
        return normalized

    @staticmethod
    def _latest_series_value(series: dict[str, float]) -> float:
        """Most recent observation in a USGS hourly-keyed series (ISO timestamps)."""
        if not series:
            return 0.0
        latest_t: datetime | None = None
        latest_v = 0.0
        for key, value in series.items():
            t = parser.isoparse(key)
            if latest_t is None or t > latest_t:
                latest_t = t
                latest_v = value
        return float(latest_v)

    @staticmethod
    def _celsius_to_fahrenheit_river(c: float) -> float:
        """USGS instantaneous water temp (00010) is degrees Celsius."""
        return round(c * 9.0 / 5.0 + 32.0, 2)

    def _water_temp_fahrenheit_for_hour(
        self, temp_series: dict[str, float], forecast_ts: datetime
    ) -> float:
        """
        Map a forecast hour to the closest USGS temperature observation in time,
        converted to °F. Falls back to latest gauge value, then 55°F if no data.
        """
        if not temp_series:
            return 55.0  # Reasonable mid-season default when gauge omits 00010
        nearest_c = self._nearest_series_value(temp_series, forecast_ts)
        if nearest_c is None:
            nearest_c = self._latest_series_value(temp_series)
        return self._celsius_to_fahrenheit_river(float(nearest_c))

    @staticmethod
    def _nearest_series_value(series: dict[str, float], target: datetime) -> float | None:
        """USGS sample whose timestamp is closest to the forecast instant (UTC-normalized)."""
        if not series:
            return None
        target_utc = target.astimezone(timezone.utc)
        best_v: float | None = None
        best_abs: float | None = None
        for key, val in series.items():
            try:
                t = parser.isoparse(key).astimezone(timezone.utc)
            except (ValueError, TypeError):
                continue
            diff = abs((t - target_utc).total_seconds())
            if best_abs is None or diff < best_abs:
                best_abs = diff
                best_v = float(val)
        return best_v

    @staticmethod
    def _parse_wind_speed_mph(speed_text: str) -> float:
        # weather.gov can return "5 mph" or "5 to 10 mph".
        cleaned = speed_text.replace("mph", "").replace("-", " ")
        parts = [p for p in cleaned.split() if p.replace(".", "", 1).isdigit()]
        if not parts:
            return 0.0
        nums = [float(p) for p in parts]
        return sum(nums) / len(nums)

    @staticmethod
    def _wind_direction_to_degrees(direction: str) -> float:
        compass = {
            "N": 0,
            "NNE": 22.5,
            "NE": 45,
            "ENE": 67.5,
            "E": 90,
            "ESE": 112.5,
            "SE": 135,
            "SSE": 157.5,
            "S": 180,
            "SSW": 202.5,
            "SW": 225,
            "WSW": 247.5,
            "W": 270,
            "WNW": 292.5,
            "NW": 315,
            "NNW": 337.5,
        }
        return compass.get(direction.strip().upper(), 0.0)

