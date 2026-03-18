import sys


def install():
    import base64
    import json
    import os
    import platform
    import traceback
    import urllib.request
    from services.updater import get_version

    crash_url = os.environ.get(
        'LIVEBRAIN_CRASH_URL', 'https://livebrain.app/api/crashes'
    )
    api_key = base64.b64decode(b'cHNZd1g3b0Nma0ZBbkpXQ2FZRU9MVXpFQ3MxTWJYYWhRRmVnNFFEaXUtVQ==').decode()
    original_hook = sys.excepthook

    def hook(exc_type, exc_value, exc_tb):
        original_hook(exc_type, exc_value, exc_tb)
        try:
            data = json.dumps({
                'app_version': get_version(),
                'os_version': platform.mac_ver()[0],
                'python_version': platform.python_version(),
                'exception_type': exc_type.__name__,
                'exception_message': str(exc_value),
                'stack_trace': ''.join(traceback.format_exception(exc_type, exc_value, exc_tb)),
            }).encode('utf-8')
            req = urllib.request.Request(
                crash_url, data=data,
                headers={'Content-Type': 'application/json', 'X-API-Key': api_key},
                method='POST'
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass

    sys.excepthook = hook
