import os
import json
import subprocess
import sys
import urllib.request
import zipfile

# Override with LIVEBRAIN_UPDATE_URL / LIVEBRAIN_MODEL_URL for self-hosted deployments
UPDATE_URL = os.environ.get('LIVEBRAIN_UPDATE_URL', 'https://livebrain.app/version.json')
MODEL_URL = os.environ.get('LIVEBRAIN_MODEL_URL', 'https://firebasestorage.googleapis.com/v0/b/livebrain-d94da.firebasestorage.app/o/models%2Fembeddinggemma-onnx.zip?alt=media')
VOSK_MODEL_URL = os.environ.get('LIVEBRAIN_VOSK_MODEL_URL', 'https://firebasestorage.googleapis.com/v0/b/livebrain-d94da.firebasestorage.app/o/models%2Fvosk-model-small-en-us-0.15.zip?alt=media')

def _app_root():
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
    if os.path.exists(os.path.join(d, 'version.json')):
        return d
    return os.path.dirname(sys.executable)

def get_version():
    version_file = os.path.join(_app_root(), 'version.json')
    with open(version_file, 'r') as f:
        return json.load(f)['version']


class Updater:
    def check_for_updates(self):
        with urllib.request.urlopen(UPDATE_URL) as response:
            data = json.loads(response.read().decode())
            latest_version = data.get('version')
            download_url = data.get('url')
            notes = data.get('notes', '')

            if latest_version and latest_version != get_version():
                return {
                    'available': True,
                    'version': latest_version,
                    'url': download_url,
                    'notes': notes,
                }
        return {'available': False}
    
    def download_update(self, url, callback=None):
        ext = '.dmg' if sys.platform == 'darwin' else '.AppImage'
        temp_file = os.path.expanduser(f"~/Downloads/Livebrain-Update{ext}")
        urllib.request.urlretrieve(url, temp_file, callback)
        return temp_file

    def open_update(self, path):
        cmd = 'open' if sys.platform == 'darwin' else 'xdg-open'
        subprocess.Popen([cmd, path])

    def download_models(self, dest_dir, progress_callback=None):
        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, 'models.zip')
        urllib.request.urlretrieve(MODEL_URL, zip_path, _progress_hook(progress_callback))
        model_subdir = os.path.join(dest_dir, 'embeddinggemma-onnx')
        os.makedirs(model_subdir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(model_subdir)
        os.remove(zip_path)

    def download_vosk_model(self, dest_dir, progress_callback=None):
        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, 'vosk-model.zip')
        urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path, _progress_hook(progress_callback))
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(dest_dir)
        os.remove(zip_path)


def _progress_hook(callback):
    if not callback:
        return None
    def hook(block_num, block_size, total_size):
        if total_size > 0:
            downloaded = block_num * block_size
            percent = min(100, int(downloaded * 100 / total_size))
            callback(percent, downloaded, total_size)
    return hook

