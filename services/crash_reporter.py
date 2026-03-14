import json
import os
import platform
import sys
import traceback
import urllib.request
from threading import Thread

from services.updater import get_version


CRASH_URL = os.environ.get(
    'LIVEBRAIN_CRASH_URL', 'https://livebrain.app/api/crashes'
)


API_KEY = 'HVEAOdoSw3R2v8ZGlkkCuGV-qk15KP-5cXMQvvkPAO4'


class CrashReporter:
    def report(self, exc_type, exc_value, exc_tb):
        data = {
            'app_version': get_version(),
            'os_version': platform.mac_ver()[0],
            'python_version': platform.python_version(),
            'exception_type': exc_type.__name__,
            'exception_message': str(exc_value),
            'stack_trace': ''.join(traceback.format_exception(exc_type, exc_value, exc_tb)),
        }
        try:
            req = urllib.request.Request(
                CRASH_URL,
                data=json.dumps(data).encode('utf-8'),
                headers={
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY,
                },
                method='POST'
            )
            urllib.request.urlopen(req)
        except Exception:
            pass


_reporter = CrashReporter()
_original_excepthook = sys.excepthook


def _excepthook(exc_type, exc_value, exc_tb):
    Thread(target=_reporter.report, args=(exc_type, exc_value, exc_tb), daemon=True).start()
    _original_excepthook(exc_type, exc_value, exc_tb)


def install():
    sys.excepthook = _excepthook
