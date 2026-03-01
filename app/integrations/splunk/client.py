"""Backward-compatible Splunk client wrapper."""

from app.clients.splunk_api import SplunkAPI
from app.services.splunk.service import SplunkService


class SplunkClient:
    """Compatibility wrapper preserving the old constructor and methods."""

    def __init__(self, base_url=None, token=None, timeout=10):
        self.service = SplunkService(api_client=SplunkAPI(base_url=base_url, token=token, timeout=timeout))

    def is_configured(self):
        return self.service.is_configured()

    def search(self, query, earliest_time="-15m", latest_time="now"):
        return self.service.search(query=query, earliest_time=earliest_time, latest_time=latest_time)
