from app.clients.splunk_api import SplunkAPI


class SplunkService:
    """Higher-level Splunk service entrypoint for command handlers."""

    def __init__(self, api_client=None):
        self.api = api_client or SplunkAPI()

    def is_configured(self):
        return self.api.is_configured()

    def search(self, query, earliest_time="-15m", latest_time="now"):
        return self.api.search_export(
            query=query,
            earliest_time=earliest_time,
            latest_time=latest_time,
        )
