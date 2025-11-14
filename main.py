import os
import sys
import subprocess
import shutil
import tempfile
import json
import threading
import re
import time
import requests
import webbrowser
from pathlib import Path
os.environ["PYWEBVIEW_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu"

try:
    import webview
except ImportError:
    print("Installing pywebview...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pywebview"], check=True)
    os.execl(sys.executable, sys.executable, *sys.argv)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installing beautifulsoup4...")
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4"], check=True)
    os.execl(sys.executable, sys.executable, *sys.argv)

FILE_NAME = "UBahnSimBerlin_Gesamt.pak"
DOWNLOAD_URL = "https://cloud.u7-trainz.de/s/fqiXTPcSCtWcLJL/download/UBahnSimBerlin_Gesamt.pak"
MIRROR_URL = "https://www.trrdroid.net/download/UBahnSimBerlin_Gesamt.pak"
WEBSITE_URL = "https://www.u7-trainz.de/downloads"
GAME_DIR_NAME = "SubwaySim 2"
MODS_DIR_NAME = "Mods"
STATUS_FILE = "mod_status.json"

class Api:
    def __init__(self):
        self.window = None
        self.selected_game_folder = None
        self.installation_cancelled = False
        self.install_thread = None
        self.backup_file_path = None

    def set_window(self, window):
        self.window = window

    def get_status(self):
        game_folder = self._find_game_folder()
        if not game_folder:
            return {
                "error": True,
                "message": f"Game folder not found. Expected at:\n{Path.home() / 'Documents' / 'My Games'}",
                "path_required": True
            }

        self.selected_game_folder = game_folder
        mods_folder = game_folder / MODS_DIR_NAME
        mod_file_path = mods_folder / FILE_NAME
        status_file_path = mods_folder / STATUS_FILE

        local_version = None
        file_exists = mod_file_path.exists()

        if status_file_path.exists():
            try:
                with open(status_file_path, 'r') as f:
                    local_version = json.load(f).get("installed_version")
            except Exception:
                pass

        if file_exists and not local_version:
            local_version = "Unknown"

        return {
            "error": False,
            "game_path": str(game_folder),
            "installed": file_exists,
            "local_version": local_version
        }

    def select_game_folder(self):
        if not self.window:
            return {"error": "Window not initialized yet."}

        try:
            start_dir = str(Path.home()) 
            result = self.window.create_file_dialog(webview.FOLDER_DIALOG, directory=start_dir)
            if not result or not result[0]:
                return {"error": "No folder selected."}

            folder_path = Path(result[0])
            if folder_path.name != GAME_DIR_NAME:
                self._send_js_update("showAlert", f"Wrong folder selected. Please select the folder named \"{GAME_DIR_NAME}\".")
                return {"error": "Wrong folder name."}

            self.selected_game_folder = folder_path
            return self.get_status()
        except Exception as e:
            return {"error": str(e)}

    def check_for_update(self, local_version):
        if not local_version or local_version == "Unknown":
            return {"error": True, "message": "Local version is unknown. Reinstallation recommended.", "force_install": True}

        remote_version = self._scrape_website_version()
        if not remote_version:
            return {"error": True, "message": "Could not retrieve remote version from website."}

        if local_version != remote_version:
            return {"update_available": True, "local": local_version, "remote": remote_version}
        else:
            return {"update_available": False, "local": local_version, "remote": remote_version}

    def install_mod(self):
        if not self.selected_game_folder:
            self._send_js_update("showErrorView", "No game folder selected or found.")
            return {"error": "No game folder selected or found."}

        self.installation_cancelled = False
        self.install_thread = threading.Thread(target=self._do_install_task, daemon=True)
        self.install_thread.start()
        return {"success": True, "message": "Installation started..."}

    def cancel_installation(self):
        self.installation_cancelled = True
        return {"success": True, "message": "Installation is being cancelled..."}

    def launch_game(self):
        try:
            if os.name == 'nt':
                subprocess.run(['start', 'steam://run/2707070'], shell=True, check=False)
            else:
                subprocess.run(['xdg-open', 'steam://run/2707070'], check=False)
            return {"success": True, "message": "Game is starting..."}
        except Exception as e:
            return {"error": True, "message": f"Error launching game: {e}"}

    def open_url(self, url):
        try:
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"error": str(e)}


    def get_settings(self):
        """Load settings from JSON file"""
        try:
            settings_file = Path("installer_settings.json")
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")

        # Default settings
        return {
            "tracking": False,
            "sound": True,
            "language": "de"
        }

    def save_settings(self, settings):
        """Save settings to JSON file"""
        try:
            with open("installer_settings.json", 'w') as f:
                json.dump(settings, f, indent=2)
            return {"success": True}
        except Exception as e:
            print(f"Error saving settings: {e}")
            return {"error": str(e)}

    def close_app(self):
        self.installation_cancelled = True
        if self.window:
            self.window.destroy()

    def _find_game_folder(self):
        if self.selected_game_folder and self.selected_game_folder.exists():
             return self.selected_game_folder

        possible_paths = []

        if os.name == 'nt':
            user_profile = os.environ.get('USERPROFILE', '')
            if user_profile:
                possible_paths.append(Path(user_profile) / "Documents" / "My Games" / GAME_DIR_NAME)
                possible_paths.append(Path(user_profile) / "OneDrive" / "Documents" / "My Games" / GAME_DIR_NAME)
                possible_paths.append(Path(user_profile) / "OneDrive" / "Dokumente" / "My Games" / GAME_DIR_NAME)
                possible_paths.append(Path(user_profile) / "OneDrive - Personal" / "Documents" / "My Games" / GAME_DIR_NAME)
                possible_paths.append(Path(user_profile) / "Dokumente" / "My Games" / GAME_DIR_NAME)
                possible_paths.append(Path(user_profile) / "OneDrive" / "Dokumente" / "My Games" / GAME_DIR_NAME)
        else:
            possible_paths.append(Path.home() / "Documents" / "My Games" / GAME_DIR_NAME)

        for path in possible_paths:
            try:
                if path.is_dir():
                    print(f"Game folder found: {path}")
                    return path
            except Exception as e:
                print(f"Error checking {path}: {e}")
                continue

        print("Game folder not found in any standard paths")
        return None

    def _scrape_website_version(self):
        try:
            page = requests.get(WEBSITE_URL, timeout=10)
            page.raise_for_status()
            soup = BeautifulSoup(page.content, "html.parser")

            text_content = page.text
            version_match = re.search(r'Beta Version:\s*([0-9]+\.[0-9]+)', text_content)
            if version_match:
                return version_match.group(1)

            all_elements = soup.find_all(text=True)
            for element in all_elements:
                text = element.strip()
                if 'Beta Version:' in text:
                    version_match = re.search(r'Beta Version:\s*([0-9]+\.[0-9]+)', text)
                    if version_match:
                        return version_match.group(1)

            print("Beta Version not found on website")
            return None
        except Exception as e:
            print(f"Error scraping website version: {e}")
            return None

    def _backup_existing_mod(self, mods_folder):
        mod_file_path = mods_folder / FILE_NAME
        if mod_file_path.exists():
            backup_name = f"{FILE_NAME}.backup.{int(time.time())}"
            self.backup_file_path = mods_folder / backup_name
            shutil.copy2(mod_file_path, self.backup_file_path)
            print(f"Backup created: {self.backup_file_path}")
            return True
        return False

    def _restore_backup(self):
        if self.backup_file_path and self.backup_file_path.exists():
            try:
                original_path = self.backup_file_path.parent / FILE_NAME
                shutil.move(self.backup_file_path, original_path)
                print("Backup restored")
                return True
            except Exception as e:
                print(f"Error restoring backup: {e}")
        return False

    def _cleanup_backup(self):
        if self.backup_file_path and self.backup_file_path.exists():
            try:
                self.backup_file_path.unlink()
                print("Backup deleted")
            except Exception as e:
                print(f"Error deleting backup: {e}")

    def _do_install_task(self):
        tmp_file_path = None
        backup_created = False
        try:
            if self.installation_cancelled:
                self._send_js_update("installCancelled")
                return

            mods_folder = self.selected_game_folder / MODS_DIR_NAME
            self._send_js_update("updateProgress", 0, f"Creating folder if needed: {mods_folder.name}")
            mods_folder.mkdir(exist_ok=True)

            if self.installation_cancelled:
                self._send_js_update("installCancelled")
                return

            target_file_path = mods_folder / FILE_NAME

            if target_file_path.exists():
                self._send_js_update("updateProgress", 5, "Creating backup of existing mod...")
                backup_created = self._backup_existing_mod(mods_folder)

            download_successful = False
            for attempt, url in enumerate([DOWNLOAD_URL, MIRROR_URL], 1):
                if self.installation_cancelled:
                    if backup_created:
                        self._restore_backup()
                    self._send_js_update("installCancelled")
                    return

                try:
                    if attempt == 2:
                        self._send_js_update("updateProgress", -1, "Primary download failed, trying mirror...")

                    self._send_js_update("updateProgress", -1, f"Starting download from server {attempt}...")

                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file_path = tmp_file.name
                        with requests.get(url, stream=True, allow_redirects=True, timeout=60) as r:
                            r.raise_for_status()
                            total_size = int(r.headers.get('content-length', 0))
                            downloaded = 0

                            if total_size > 0:
                                self._send_js_update("updateProgress", 10, f"Download started ({total_size // 1024**2} MB)", 0, total_size)

                            for chunk in r.iter_content(chunk_size=8192):
                                if self.installation_cancelled:
                                    if backup_created:
                                        self._restore_backup()
                                    self._send_js_update("installCancelled")
                                    return

                                if not chunk:
                                    continue

                                tmp_file.write(chunk)
                                downloaded += len(chunk)

                                if total_size > 0:
                                    download_percent = int((downloaded / total_size) * 80) + 10
                                    self._send_js_update("updateProgress", download_percent,
                                        f"Downloading from server {attempt}... {int((downloaded / total_size) * 100)}%",
                                        downloaded, total_size)
                                else:
                                    self._send_js_update("updateProgress", -1,
                                        f"Downloading from server {attempt}... {downloaded // 1024**2} MB",
                                        downloaded, downloaded * 2)

                    download_successful = True
                    break

                except requests.RequestException as e:
                    if tmp_file_path and os.path.exists(tmp_file_path):
                        try:
                            os.remove(tmp_file_path)
                        except OSError:
                            pass
                        tmp_file_path = None

                    if attempt == 1:
                        print(f"Primary download failed: {e}")
                        continue
                    else:
                        if backup_created:
                            self._restore_backup()
                        raise Exception(f"Download failed from both servers. Last error: {e}")

            if not download_successful:
                if backup_created:
                    self._restore_backup()
                raise Exception("Download could not be completed")

            if self.installation_cancelled:
                if backup_created:
                    self._restore_backup()
                self._send_js_update("installCancelled")
                return

            self._send_js_update("updateProgress", 95, "Download complete. Installing mod...")
            shutil.move(tmp_file_path, target_file_path)
            tmp_file_path = None

            if backup_created:
                self._cleanup_backup()

            self._send_js_update("updateProgress", 100, "Installation complete. Saving version...")
            latest_version = self._scrape_website_version()
            if not latest_version:
                latest_version = "Unknown"
            self._set_local_version(mods_folder, latest_version)

            self._send_js_update("installComplete", True, f"Installed version: {latest_version}")

        except Exception as e:
            print(f"Installation error: {e}")
            if backup_created:
                self._restore_backup()
            self._send_js_update("installComplete", False, f"Error: {str(e)}")
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except OSError:
                    pass

    def _set_local_version(self, mods_folder, version_string):
        status_file_path = mods_folder / STATUS_FILE
        try:
            with open(status_file_path, 'w') as f:
                json.dump({"installed_version": version_string}, f, indent=2)
        except OSError as e:
            print(f"Error writing status JSON: {e}")


    def _send_js_update(self, function_name, *args):
        if self.window:
            try:
                if function_name == "installCancelled":
                    js_code = f"{function_name}()"
                else:
                    js_args = ", ".join([json.dumps(arg) for arg in args])
                    js_code = f"{function_name}({js_args})"
                self.window.evaluate_js(js_code)
            except Exception as e:
                print(f"Error sending JS update: {e}")

def on_loaded():
    api.set_window(main_window)
    main_window.show()

    def delayed_status_check():
        time.sleep(0.5)
        main_window.evaluate_js("checkInitialStatus()")

    status_thread = threading.Thread(target=delayed_status_check, daemon=True)
    status_thread.start()

if __name__ == '__main__':
    api = Api()



    main_window = webview.create_window(
        'SubwaySim2 USB Installer v1.0 Beta',
        'index.html',
        js_api=api,
        width=800,
        height=600,
        resizable=False,
        hidden=True
    )

    webview.start(on_loaded, debug=True)
