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


if getattr(sys, 'frozen', False):
    
    if hasattr(sys, '_MEIPASS'):
        
        BASE_PATH = Path(sys._MEIPASS)
    else:
        
        BASE_PATH = Path(sys.executable).parent
else:
    
    BASE_PATH = Path(__file__).parent


os.environ["PYWEBVIEW_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu"


import webview
from bs4 import BeautifulSoup

FILE_NAME = "UBahnSimBerlin_Gesamt.pak"
DOWNLOAD_URL = "https://cloud.u7-trainz.de/s/fqiXTPcSCtWcLJL/download/UBahnSimBerlin_Gesamt.pak"
MIRROR_URL = "https://www.trrdroid.net/download/UBahnSimBerlin_Gesamt.pak"
WEBSITE_URL = "https://www.u7-trainz.de/downloads"
GAME_DIR_NAME = "SubwaySim 2"
MODS_DIR_NAME = "Mods"
STATUS_FILE = "mod_status.json"

DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_TIMEOUT = 60
DOWNLOAD_PROGRESS_INTERVAL = 2.0

INSTALLER_VERSION = "1.0"
INSTALLER_UPDATE_INFO_URL = "https://onejanik.xyz/sws2_usb_installer/version.json"

DEFAULT_LANGUAGE = "de"

MESSAGES = {
    "de": {
        "no_game_folder": "Kein Spielordner ausgewählt oder gefunden.",
        "installation_already_running": "Eine Installation läuft bereits.",
        "creating_mods_folder": "Mods-Ordner wird erstellt...",
        "creating_backup": "Backup des vorhandenen Mods wird erstellt...",
        "primary_download_failed": "Primärer Download fehlgeschlagen, versuche Spiegelserver...",
        "starting_download_from_server": "Starte Download von Server {server}...",
        "download_started": "Download gestartet ({size_mb} MB)",
        "downloading_from_server_percent": "Lade von Server {server}... {percent}%",
        "downloading_from_server_mb": "Lade von Server {server}... {mb} MB",
        "download_failed_both_servers": "Download von beiden Servern fehlgeschlagen. Letzter Fehler: {error}",
        "download_could_not_be_completed": "Download konnte nicht abgeschlossen werden.",
        "download_complete_install": "Download abgeschlossen. Mod wird installiert...",
        "installation_complete_saving": "Installation abgeschlossen. Version wird gespeichert...",
        "installation_failed": "Installation fehlgeschlossen: {error}",
        "restoring_backup": "Installation abgebrochen. Ursprüngliche Dateien werden wiederhergestellt...",
        "cleanup_temp": "Temporäre Dateien werden aufgeräumt..."
    },
    "en": {
        "no_game_folder": "No game folder selected or found.",
        "installation_already_running": "Installation is already running.",
        "creating_mods_folder": "Creating mods folder...",
        "creating_backup": "Creating backup of existing mod...",
        "primary_download_failed": "Primary download failed, trying mirror...",
        "starting_download_from_server": "Starting download from server {server}...",
        "download_started": "Download started ({size_mb} MB)",
        "downloading_from_server_percent": "Downloading from server {server}... {percent}%",
        "downloading_from_server_mb": "Downloading from server {server}... {mb} MB",
        "download_failed_both_servers": "Download failed from both servers. Last error: {error}",
        "download_could_not_be_completed": "Download could not be completed.",
        "download_complete_install": "Download complete. Installing mod...",
        "installation_complete_saving": "Installation complete. Saving version...",
        "installation_failed": "Installation failed: {error}",
        "restoring_backup": "Installation cancelled. Restoring original files...",
        "cleanup_temp": "Cleaning up temporary files..."
    }
}


class Api:
    def __init__(self):
        self.window = None
        self.selected_game_folder = None
        self.installation_cancelled = False
        self.install_thread = None
        self.backup_file_path = None
        self.language = DEFAULT_LANGUAGE

    def _msg(self, key, **kwargs):
        lang = self.language or DEFAULT_LANGUAGE
        lang_dict = MESSAGES.get(lang, MESSAGES.get(DEFAULT_LANGUAGE, {}))
        template = lang_dict.get(key) or MESSAGES.get("en", {}).get(key) or key
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    def _compare_versions(self, v1, v2):
        def norm(v):
            return [int(x) for x in str(v).split(".")]
        a = norm(v1)
        b = norm(v2)
        max_len = max(len(a), len(b))
        a += [0] * (max_len - len(a))
        b += [0] * (max_len - len(b))
        if a > b:
            return 1
        if a < b:
            return -1
        return 0

    def set_window(self, window):
        self.window = window

    def set_language(self, language):
        if language not in MESSAGES:
            language = DEFAULT_LANGUAGE
        self.language = language
        return {"success": True, "language": self.language}

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
        status_file_path = self._get_status_file_path(mods_folder)
        legacy_status_file_path = mods_folder / STATUS_FILE

        local_version = None
        file_exists = mod_file_path.exists()

        if status_file_path.exists():
            try:
                with open(status_file_path, 'r') as f:
                    local_version = json.load(f).get("installed_version")
            except Exception:
                pass
        elif legacy_status_file_path.exists():
            try:
                with open(legacy_status_file_path, 'r') as f:
                    data = json.load(f)
                    local_version = data.get("installed_version")
                try:
                    status_file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(status_file_path, 'w') as f:
                        json.dump(data, f, indent=2)
                except Exception as e:
                    print(f"Error migrating status file to LocalAppData: {e}")
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
                self._send_js_update(
                    "showAlert",
                    "Wrong folder selected. Please select the folder named \"{}\".".format(GAME_DIR_NAME),
                    "danger"
                )
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
        if not self.selected_game_folder or not self.selected_game_folder.exists():
            self.selected_game_folder = self._find_game_folder()

        if not self.selected_game_folder:
            msg = self._msg("no_game_folder")
            self._send_js_update("showErrorView", msg)
            return {"error": msg}

        if self.install_thread and self.install_thread.is_alive():
            return {"error": self._msg("installation_already_running")}

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
        try:
            settings_file = Path("installer_settings.json")
            if settings_file.exists():
                with open(settings_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading settings: {e}")

        return {
            "tracking": False,
            "sound": True,
            "language": "de"
        }

    def save_settings(self, settings):
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

    def check_installer_update(self):
        try:
            resp = requests.get(INSTALLER_UPDATE_INFO_URL, timeout=10)
            resp.raise_for_status()
            info = resp.json()

            remote_version = str(info.get("version", "")).strip()
            download_url = info.get("url")

            if not remote_version or not download_url:
                return {
                    "error": True,
                    "message": "Invalid update info from server."
                }

            cmp = self._compare_versions(remote_version, INSTALLER_VERSION)

            if cmp > 0:
                return {
                    "update_available": True,
                    "local": INSTALLER_VERSION,
                    "remote": remote_version,
                    "url": download_url
                }
            else:
                return {
                    "update_available": False,
                    "local": INSTALLER_VERSION,
                    "remote": remote_version
                }
        except Exception as e:
            return {
                "error": True,
                "message": f"Error checking installer update: {e}"
            }

    def update_installer(self, download_url, filename=None):
        if not download_url:
            return {"error": True, "message": "No download URL provided."}

        try:
            if filename is None:
                filename = os.path.basename(download_url) or "installer_new.exe"

            with tempfile.TemporaryDirectory() as tmpdir:
                tmp_path = Path(tmpdir) / filename

                with requests.get(download_url, stream=True, timeout=60) as r:
                    r.raise_for_status()
                    with open(tmp_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if not chunk:
                                continue
                            f.write(chunk)

                if os.name == "nt":
                    subprocess.Popen(
                        ["start", "", str(tmp_path)],
                        shell=True
                    )
                else:
                    subprocess.Popen(
                        ["xdg-open", str(tmp_path)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )

            os._exit(0)
        except Exception as e:
            return {"error": True, "message": f"Error updating installer: {e}"}

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

    def _get_status_file_path(self, mods_folder=None):
        local_app_data = os.getenv('LOCALAPPDATA')
        if local_app_data:
            base = Path(local_app_data) / "SubwaySim2_USB_Installer"
            try:
                base.mkdir(parents=True, exist_ok=True)
            except OSError as e:
                print(f"Error creating LocalAppData status folder: {e}")
            return base / STATUS_FILE
        if mods_folder is not None:
            return mods_folder / STATUS_FILE
        return Path(STATUS_FILE)

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
                self._send_js_update("updateProgress", -1, self._msg("restoring_backup"), 0, 0)
                original_path = self.backup_file_path.parent / FILE_NAME
                shutil.move(self.backup_file_path, original_path)
                print("Backup restored")
                self.backup_file_path = None
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
        self.backup_file_path = None

    def _do_install_task(self):
        tmp_file_path = None
        backup_created = False
        try:
            if self.installation_cancelled:
                self._send_js_update("installCancelled")
                return

            mods_folder = self.selected_game_folder / MODS_DIR_NAME
            self._send_js_update("updateProgress", 0, self._msg("creating_mods_folder"), 0, 0)
            mods_folder.mkdir(exist_ok=True)

            if self.installation_cancelled:
                self._send_js_update("installCancelled")
                return

            target_file_path = mods_folder / FILE_NAME

            if target_file_path.exists():
                self._send_js_update("updateProgress", 5, self._msg("creating_backup"), 0, 0)
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
                        self._send_js_update("updateProgress", -1, self._msg("primary_download_failed"), 0, 0)

                    self._send_js_update(
                        "updateProgress",
                        -1,
                        self._msg("starting_download_from_server", server=attempt),
                        0,
                        0
                    )

                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file_path = tmp_file.name

                        with requests.get(url, stream=True, allow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as r:
                            r.raise_for_status()
                            total_size = int(r.headers.get('content-length', 0))
                            downloaded = 0

                            last_ui_update = 0.0

                            if total_size > 0:
                                size_mb = total_size // 1024**2
                                self._send_js_update(
                                    "updateProgress",
                                    10,
                                    self._msg("download_started", size_mb=size_mb),
                                    0,
                                    total_size
                                )
                                last_ui_update = time.time()

                            for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                                if self.installation_cancelled:
                                    if backup_created:
                                        self._restore_backup()
                                    self._send_js_update("installCancelled")
                                    return

                                if not chunk:
                                    continue

                                tmp_file.write(chunk)
                                downloaded += len(chunk)

                                now = time.time()
                                should_update = (now - last_ui_update) >= DOWNLOAD_PROGRESS_INTERVAL

                                is_finished = (total_size > 0 and downloaded >= total_size)

                                if not (should_update or is_finished):
                                    continue

                                last_ui_update = now

                                if total_size > 0:
                                    percent_total = int((downloaded / total_size) * 100)
                                    download_percent = int((downloaded / total_size) * 80) + 10

                                    self._send_js_update(
                                        "updateProgress",
                                        download_percent,
                                        self._msg(
                                            "downloading_from_server_percent",
                                            server=attempt,
                                            percent=percent_total
                                        ),
                                        downloaded,
                                        total_size
                                    )
                                else:
                                    mb = downloaded // 1024**2
                                    self._send_js_update(
                                        "updateProgress",
                                        -1,
                                        self._msg(
                                            "downloading_from_server_mb",
                                            server=attempt,
                                            mb=mb
                                        ),
                                        downloaded,
                                        downloaded * 2
                                    )

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
                        raise Exception(self._msg("download_failed_both_servers", error=str(e)))

            if not download_successful:
                if backup_created:
                    self._restore_backup()
                raise Exception(self._msg("download_could_not_be_completed"))

            if self.installation_cancelled:
                if backup_created:
                    self._restore_backup()
                self._send_js_update("installCancelled")
                return

            self._send_js_update("updateProgress", 95, self._msg("download_complete_install"), 0, 0)
            shutil.move(tmp_file_path, target_file_path)
            tmp_file_path = None

            if backup_created:
                self._cleanup_backup()

            self._send_js_update("updateProgress", 100, self._msg("installation_complete_saving"), 0, 0)
            latest_version = self._scrape_website_version()
            if not latest_version:
                latest_version = "Unknown"
            self._set_local_version(mods_folder, latest_version)

            self._send_js_update("installComplete", True, f"Installed version: {latest_version}")

        except Exception as e:
            print(f"Installation error: {e}")
            if backup_created:
                self._restore_backup()
            self._send_js_update("installComplete", False, self._msg("installation_failed", error=str(e)))
        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    self._send_js_update("updateProgress", -1, self._msg("cleanup_temp"), 0, 0)
                    os.remove(tmp_file_path)
                except OSError:
                    pass
            self.installation_cancelled = False

    def _set_local_version(self, mods_folder, version_string):
        status_file_path = self._get_status_file_path(mods_folder)
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


if __name__ == '__main__':
    api = Api()

    
    html_path = str(BASE_PATH / 'index.html')
    
    main_window = webview.create_window(
        'SubwaySim2 USB Installer v1.0 Beta',
        html_path,  
        width=800,
        height=600,
        resizable=False
    )

    def expose_api(window):
        window.expose(
            api.get_status,
            api.select_game_folder,
            api.check_for_update,
            api.install_mod,
            api.cancel_installation,
            api.launch_game,
            api.open_url,
            api.get_settings,
            api.save_settings,
            api.set_language,
            api.close_app,
            api.check_installer_update,
            api.update_installer
        )
        api.set_window(window)
        print("API functions exposed")

    webview.start(expose_api, main_window, debug=False)
