import os

import requests


class SplunkAPI:
    """Low-level Splunk API client."""

    def __init__(self, base_url=None, token=None, timeout=10):
        self.base_url = (base_url or os.getenv("SPLUNK_BASE_URL") or "").rstrip("/")
        self.token = token or os.getenv("SPLUNK_TOKEN")
        self.timeout = timeout

    def is_configured(self):
        return bool(self.base_url and self.token)

    def search_export(self, query, earliest_time="-15m", latest_time="now"):
        if not self.is_configured():
            raise ValueError("Splunk API is not configured. Set SPLUNK_BASE_URL and SPLUNK_TOKEN.")

        url = f"{self.base_url}/services/search/jobs/export"
        headers = {"Authorization": f"Bearer {self.token}"}
        data = {
            "search": query,
            "output_mode": "json",
            "earliest_time": earliest_time,
            "latest_time": latest_time,
        }

        response = requests.post(url, headers=headers, data=data, timeout=self.timeout)
        response.raise_for_status()
        return response.text
