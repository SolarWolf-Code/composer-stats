from composer_stats_api.app import app as application


# Backward-compat import for ASGI servers expecting app variable here
app = application
