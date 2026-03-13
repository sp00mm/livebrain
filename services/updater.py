import os
import json
import urllib.request
import zipfile

# Override with LIVEBRAIN_UPDATE_URL / LIVEBRAIN_MODEL_URL for self-hosted deployments
UPDATE_URL = os.environ.get('LIVEBRAIN_UPDATE_URL', 'https://livebrain.app/version.json')
MODEL_URL = os.environ.get('LIVEBRAIN_MODEL_URL', 'https://axa3tfnfy6dd.objectstorage.us-chicago-1.oci.customer-oci.com/p/V4u-uKDpP_p2kHbWEZPQZ0sEBe0-qZCqW5i3yu3fK-VC-ZIgCxd8rm7wdK6fL6NV/n/axa3tfnfy6dd/b/livebrain-models/o/embeddinggemma-onnx.zip')

def get_version():
    version_file = os.path.join(os.path.dirname(__file__), '..', 'version.json')
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
        temp_file = os.path.expanduser("~/Downloads/LiveBrain-Update.dmg")
        urllib.request.urlretrieve(url, temp_file, callback)
        return temp_file
    
    def open_dmg(self, path):
        import subprocess
        subprocess.Popen(['open', path])

    def download_models(self, dest_dir, progress_callback=None):
        os.makedirs(dest_dir, exist_ok=True)
        zip_path = os.path.join(dest_dir, "models.zip")
        
        def report_progress(block_num, block_size, total_size):
            if progress_callback and total_size > 0:
                downloaded = block_num * block_size
                percent = min(100, int(downloaded * 100 / total_size))
                progress_callback(percent, downloaded, total_size)
        
        urllib.request.urlretrieve(MODEL_URL, zip_path, report_progress)
        model_subdir = os.path.join(dest_dir, "embeddinggemma-onnx")
        os.makedirs(model_subdir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(model_subdir)
        
        os.remove(zip_path)

