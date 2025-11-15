# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import shutil
import tempfile
import json
import time
import requests
import re
from pathlib import Path

# UTF-8 Encoding für Windows erzwingen
if sys.platform == 'win32':
    # Setze Console auf UTF-8
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleCP(65001)
        kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

    # Setze Python Encoding
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr.reconfigure(encoding='utf-8')

# Rich imports für Terminal-UI
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn
    from rich.prompt import Prompt, Confirm
    from rich.table import Table
    from rich import box
    from rich.tree import Tree
    from rich.live import Live
except ImportError:
    print("Installiere benötigte Pakete...")
    subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)
    os.execl(sys.executable, sys.executable, *sys.argv)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installiere benötigte Pakete...")
    subprocess.run([sys.executable, "-m", "pip", "install", "beautifulsoup4"], check=True)
    os.execl(sys.executable, sys.executable, *sys.argv)

# Konstanten
FILE_NAME = "UBahnSimBerlin_Gesamt.pak"
DOWNLOAD_URL = "https://cloud.u7-trainz.de/s/fqiXTPcSCtWcLJL/download/UBahnSimBerlin_Gesamt.pak"
MIRROR_URL = "https://www.trrdroid.net/download/UBahnSimBerlin_Gesamt.pak"
WEBSITE_URL = "https://www.u7-trainz.de/downloads"
GAME_DIR_NAME = "SubwaySim 2"
MODS_DIR_NAME = "Mods"
STATUS_FILE = "mod_status.json"

DOWNLOAD_CHUNK_SIZE = 8192
DOWNLOAD_TIMEOUT = 60

INSTALLER_VERSION = "1.0"

DEFAULT_LANGUAGE = "de"

# Icons für verschiedene Plattformen
if sys.platform == 'win32':
    # Einfachere Icons für Windows CMD
    ICON_SUCCESS = "[+]"
    ICON_ERROR = "[x]"
    ICON_PROGRESS = "[~]"
    ICON_PENDING = "[ ]"
    ICON_WARNING = "[!]"
else:
    # Unicode Icons für Linux/Mac
    ICON_SUCCESS = "✓"
    ICON_ERROR = "✗"
    ICON_PROGRESS = "●"
    ICON_PENDING = "○"
    ICON_WARNING = "⚠"

# Nachrichten
MESSAGES = {
    "de": {
        "title": "U-Bahn Berlin Mod Installer",
        "subtitle": "Installiere die U-Bahn Berlin fuer SubwaySim 2",
        "welcome": "Willkommen beim U-Bahn Berlin Installer!",
        "checking_status": "Ueberpruefe Installation",
        "game_found": "Spiel gefunden",
        "game_not_found": "Spiel nicht gefunden",
        "mod_installed": "Mod ist installiert",
        "mod_not_installed": "Mod ist nicht installiert",
        "update_available": "Update verfuegbar",
        "up_to_date": "Alles aktuell",
        "recommendation": "Empfehlung",
        "what_to_do": "Was moechtest du tun?",
        "install_mod": "Mod jetzt installieren",
        "update_mod": "Mod jetzt aktualisieren",
        "reinstall_mod": "Mod neu installieren",
        "launch_game": "Spiel starten",
        "advanced_options": "Erweiterte Optionen",
        "exit": "Beenden",
        "step_find_game": "Spielordner suchen",
        "step_create_mods": "Vorbereitung",
        "step_backup": "Sicherung erstellen",
        "step_download": "Mod herunterladen",
        "step_install": "Installation",
        "step_cleanup": "Abschliessen",
        "step_complete": "Fertig!",
        "installation_steps": "Installation",
        "please_wait": "Bitte warten",
        "success_title": "Installation erfolgreich!",
        "success_message": "Die U-Bahn Berlin wurde erfolgreich installiert.\nDu kannst jetzt das Spiel starten!",
        "error_title": "Fehler",
        "game_not_found_detail": "SubwaySim 2 konnte nicht gefunden werden.\n\nBitte stelle sicher, dass das Spiel installiert und\nmindestens einmal gestartet wurde.",
        "manual_path": "Spielordner manuell auswaehlen",
        "press_enter": "Druecke Enter zum Fortfahren",
        "installation_time": "Installationszeit",
        "current_version": "Aktuelle Version",
        "available_version": "Verfuegbare Version",
        "status_ok": "Alles in Ordnung! Der Mod ist auf dem neuesten Stand.",
        "status_update": "Ein Update ist verfuegbar! Es wird empfohlen, zu aktualisieren.",
        "status_not_installed": "Der Mod ist noch nicht installiert.\nInstalliere ihn, um die U-Bahn Berlin zu spielen!",
        "advanced_menu_title": "Erweiterte Optionen",
        "change_language": "Sprache aendern",
        "show_details": "Details anzeigen",
        "back": "Zurueck",
    },
    "en": {
        "title": "U-Bahn Berlin Mod Installer",
        "subtitle": "Install the U-Bahn Berlin for SubwaySim 2",
        "welcome": "Welcome to the U-Bahn Berlin Installer!",
        "checking_status": "Checking installation",
        "game_found": "Game found",
        "game_not_found": "Game not found",
        "mod_installed": "Mod is installed",
        "mod_not_installed": "Mod is not installed",
        "update_available": "Update available",
        "up_to_date": "Up to date",
        "recommendation": "Recommendation",
        "what_to_do": "What would you like to do?",
        "install_mod": "Install mod now",
        "update_mod": "Update mod now",
        "reinstall_mod": "Reinstall mod",
        "launch_game": "Launch game",
        "advanced_options": "Advanced options",
        "exit": "Exit",
        "step_find_game": "Find game folder",
        "step_create_mods": "Preparation",
        "step_backup": "Create backup",
        "step_download": "Download mod",
        "step_install": "Installation",
        "step_cleanup": "Finishing",
        "step_complete": "Complete!",
        "installation_steps": "Installation",
        "please_wait": "Please wait",
        "success_title": "Installation successful!",
        "success_message": "The U-Bahn Berlin has been successfully installed.\nYou can now start the game!",
        "error_title": "Error",
        "game_not_found_detail": "SubwaySim 2 could not be found.\n\nPlease make sure the game is installed and\nhas been started at least once.",
        "manual_path": "Select game folder manually",
        "press_enter": "Press Enter to continue",
        "installation_time": "Installation time",
        "current_version": "Current version",
        "available_version": "Available version",
        "status_ok": "All good! The mod is up to date.",
        "status_update": "An update is available! It is recommended to update.",
        "status_not_installed": "The mod is not yet installed.\nInstall it to play the U-Bahn Berlin!",
        "advanced_menu_title": "Advanced Options",
        "change_language": "Change language",
        "show_details": "Show details",
        "back": "Back",
    }
}


class InstallationStep:
    def __init__(self, name, key):
        self.name = name
        self.key = key
        self.status = "pending"
        self.start_time = None
        self.end_time = None
        self.error = None

    def start(self):
        self.status = "in_progress"
        self.start_time = time.time()

    def complete(self):
        self.status = "completed"
        self.end_time = time.time()

    def fail(self, error=None):
        self.status = "failed"
        self.end_time = time.time()
        self.error = error

    def get_duration(self):
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None


class TerminalInstaller:
    def __init__(self):
        # Console mit Windows-Unterstützung
        self.console = Console(
            force_terminal=True,
            legacy_windows=False,
            force_interactive=True
        )
        self.selected_game_folder = None
        self.installation_cancelled = False
        self.backup_file_path = None
        self.language = DEFAULT_LANGUAGE
        self.settings = self.load_settings()
        self.language = self.settings.get("language", DEFAULT_LANGUAGE)

        # Status info
        self.game_folder = None
        self.mod_installed = False
        self.local_version = None
        self.remote_version = None

    def msg(self, key, **kwargs):
        lang_dict = MESSAGES.get(self.language, MESSAGES.get(DEFAULT_LANGUAGE, {}))
        template = lang_dict.get(key) or MESSAGES.get("en", {}).get(key) or key
        try:
            return template.format(**kwargs)
        except Exception:
            return template

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def show_header(self):
        title_text = f"[bold cyan]{self.msg('title')}[/bold cyan]\n[dim]{self.msg('subtitle')}[/dim]"
        self.console.print(Panel(title_text, box=box.DOUBLE, border_style="cyan"))
        self.console.print()

    def create_steps_panel(self, steps):
        tree = Tree(f"[bold cyan]{self.msg('installation_steps')}[/bold cyan]")

        for step in steps:
            if step.status == "completed":
                icon = f"[green]{ICON_SUCCESS}[/green]"
                style = "green"
            elif step.status == "in_progress":
                icon = f"[yellow]{ICON_PROGRESS}[/yellow]"
                style = "yellow bold"
            elif step.status == "failed":
                icon = f"[red]{ICON_ERROR}[/red]"
                style = "red"
            else:
                icon = f"[dim]{ICON_PENDING}[/dim]"
                style = "dim"

            time_info = ""
            if step.get_duration():
                time_info = f" [dim]({step.get_duration():.1f}s)[/dim]"

            step_text = f"{icon} [{style}]{self.msg(step.key)}[/{style}]{time_info}"

            if step.error:
                step_text += f"\n  [red]-> {step.error}[/red]"

            tree.add(step_text)

        return Panel(tree, border_style="cyan", box=box.ROUNDED)

    def find_game_folder(self):
        if self.selected_game_folder and self.selected_game_folder.exists():
            return self.selected_game_folder

        possible_paths = []

        if os.name == 'nt':
            user_profile = os.environ.get('USERPROFILE', '')
            if user_profile:
                possible_paths.extend([
                    Path(user_profile) / "Documents" / "My Games" / GAME_DIR_NAME,
                    Path(user_profile) / "OneDrive" / "Documents" / "My Games" / GAME_DIR_NAME,
                    Path(user_profile) / "OneDrive" / "Dokumente" / "My Games" / GAME_DIR_NAME,
                    Path(user_profile) / "Dokumente" / "My Games" / GAME_DIR_NAME,
                ])
        else:
            possible_paths.append(Path.home() / "Documents" / "My Games" / GAME_DIR_NAME)

        for path in possible_paths:
            try:
                if path.is_dir():
                    return path
            except Exception:
                continue

        return None

    def get_status_file_path(self, mods_folder=None):
        local_app_data = os.getenv('LOCALAPPDATA')
        if local_app_data:
            base = Path(local_app_data) / "SubwaySim2_USB_Installer"
            try:
                base.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            return base / STATUS_FILE
        if mods_folder is not None:
            return mods_folder / STATUS_FILE
        return Path(STATUS_FILE)

    def scrape_website_version(self):
        try:
            page = requests.get(WEBSITE_URL, timeout=10)
            page.raise_for_status()

            version_match = re.search(r'Beta Version:\s*([0-9]+\.[0-9]+)', page.text)
            if version_match:
                return version_match.group(1)

            return None
        except Exception:
            return None

    def format_size(self, bytes_size):
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_size < 1024.0:
                return f"{bytes_size:.1f} {unit}"
            bytes_size /= 1024.0
        return f"{bytes_size:.1f} TB"

    def format_time(self, seconds):
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def check_status_silent(self):
        """Ueberprueft den Status ohne UI-Output"""
        self.game_folder = self.find_game_folder()

        if not self.game_folder:
            return False

        self.selected_game_folder = self.game_folder
        mods_folder = self.game_folder / MODS_DIR_NAME
        mod_file_path = mods_folder / FILE_NAME
        status_file_path = self.get_status_file_path(mods_folder)

        self.local_version = None
        self.mod_installed = mod_file_path.exists()

        if status_file_path.exists():
            try:
                with open(status_file_path, 'r', encoding='utf-8') as f:
                    self.local_version = json.load(f).get("installed_version")
            except Exception:
                pass

        if self.mod_installed and not self.local_version:
            self.local_version = "Unknown"

        self.remote_version = self.scrape_website_version()

        return True

    def show_startup_screen(self):
        """Zeigt den Startbildschirm mit automatischer Status-Ueberpruefung"""
        self.clear_screen()
        self.show_header()

        # Automatische Status-Ueberpruefung
        with self.console.status(f"[bold cyan]{self.msg('checking_status')}...[/bold cyan]", spinner="dots"):
            time.sleep(0.5)
            game_found = self.check_status_silent()
            time.sleep(0.5)

        self.console.print()

        # Status-Anzeige
        status_items = []

        if game_found:
            status_items.append((ICON_SUCCESS, "green", self.msg("game_found"), str(self.game_folder)))
        else:
            status_items.append((ICON_ERROR, "red", self.msg("game_not_found"), self.msg("game_not_found_detail")))

        if self.mod_installed:
            version_text = f"{self.msg('current_version')}: {self.local_version or 'Unknown'}"
            status_items.append((ICON_SUCCESS, "green", self.msg("mod_installed"), version_text))
        else:
            status_items.append((ICON_PENDING, "yellow", self.msg("mod_not_installed"), ""))

        if self.remote_version and self.local_version and self.local_version != self.remote_version:
            update_text = f"{self.msg('available_version')}: {self.remote_version}"
            status_items.append((ICON_WARNING, "yellow", self.msg("update_available"), update_text))
        elif self.remote_version and self.local_version:
            status_items.append((ICON_SUCCESS, "green", self.msg("up_to_date"), ""))

        # Status-Panel erstellen
        status_table = Table(show_header=False, box=None, padding=(0, 1))
        status_table.add_column("", style="bold", width=3)
        status_table.add_column("", width=25)
        status_table.add_column("", style="dim")

        for icon, color, label, detail in status_items:
            status_table.add_row(
                f"[{color}]{icon}[/{color}]",
                f"[{color}]{label}[/{color}]",
                detail
            )

        self.console.print(Panel(status_table, title="[bold]Status[/bold]", border_style="cyan", box=box.ROUNDED))
        self.console.print()

        # Empfehlung
        if not game_found:
            recommendation = self.msg("game_not_found_detail")
            rec_style = "red"
        elif not self.mod_installed:
            recommendation = self.msg("status_not_installed")
            rec_style = "yellow"
        elif self.remote_version and self.local_version != self.remote_version:
            recommendation = self.msg("status_update")
            rec_style = "yellow"
        else:
            recommendation = self.msg("status_ok")
            rec_style = "green"

        self.console.print(Panel(
            f"[{rec_style}]{recommendation}[/{rec_style}]",
            title=f"[bold]{self.msg('recommendation')}[/bold]",
            border_style=rec_style,
            box=box.ROUNDED
        ))
        self.console.print()

    def show_main_menu(self):
        """Zeigt ein vereinfachtes Hauptmenue basierend auf dem Status"""
        menu_items = []

        if not self.game_folder:
            menu_items.append(("1", "manual_path"))
            menu_items.append(("0", "exit"))
        elif not self.mod_installed:
            menu_items.append(("1", "install_mod"))
            menu_items.append(("2", "advanced_options"))
            menu_items.append(("0", "exit"))
        elif self.remote_version and self.local_version != self.remote_version:
            menu_items.append(("1", "update_mod"))
            menu_items.append(("2", "launch_game"))
            menu_items.append(("3", "advanced_options"))
            menu_items.append(("0", "exit"))
        else:
            menu_items.append(("1", "launch_game"))
            menu_items.append(("2", "reinstall_mod"))
            menu_items.append(("3", "advanced_options"))
            menu_items.append(("0", "exit"))

        # Menue anzeigen
        menu_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        menu_table.add_column("", style="cyan bold", width=8)
        menu_table.add_column("", style="white")

        for option, key in menu_items:
            menu_table.add_row(option, self.msg(key))

        self.console.print(Panel(
            menu_table,
            title=f"[bold]{self.msg('what_to_do')}[/bold]",
            border_style="green"
        ))
        self.console.print()

        choices = [item[0] for item in menu_items]
        choice = Prompt.ask(
            "[yellow]>[/yellow]",
            choices=choices,
            default="1" if "1" in choices else "0"
        )

        return choice, menu_items

    def show_advanced_menu(self):
        """Zeigt erweiterte Optionen"""
        self.clear_screen()
        self.show_header()

        menu_table = Table(show_header=False, box=box.SIMPLE, padding=(0, 2))
        menu_table.add_column("", style="cyan bold", width=8)
        menu_table.add_column("", style="white")

        menu_table.add_row("1", self.msg("change_language"))
        menu_table.add_row("2", self.msg("show_details"))
        menu_table.add_row("3", self.msg("manual_path"))
        menu_table.add_row("0", self.msg("back"))

        self.console.print(Panel(
            menu_table,
            title=f"[bold]{self.msg('advanced_menu_title')}[/bold]",
            border_style="blue"
        ))
        self.console.print()

        choice = Prompt.ask("[yellow]>[/yellow]", choices=["0", "1", "2", "3"], default="0")

        if choice == "1":
            self.change_language()
        elif choice == "2":
            self.show_details()
        elif choice == "3":
            self.select_folder_manually()

        return choice != "0"

    def change_language(self):
        """Aendert die Sprache"""
        new_lang = Prompt.ask("Language / Sprache", choices=["de", "en"], default=self.language)
        self.language = new_lang
        self.settings["language"] = new_lang
        self.save_settings()
        self.console.print(f"[green]{ICON_SUCCESS} Language changed / Sprache geaendert[/green]")
        time.sleep(1)

    def show_details(self):
        """Zeigt detaillierte Informationen"""
        self.clear_screen()
        self.show_header()

        details_table = Table(show_header=False, box=box.ROUNDED)
        details_table.add_column("", style="cyan", width=25)
        details_table.add_column("", style="white")

        details_table.add_row("Installer Version", INSTALLER_VERSION)
        details_table.add_row(self.msg("game_folder"), str(self.game_folder) if self.game_folder else "Not found")
        details_table.add_row(self.msg("mod_installed"), "Yes" if self.mod_installed else "No")
        details_table.add_row(self.msg("current_version"), self.local_version or "Unknown")
        details_table.add_row(self.msg("available_version"), self.remote_version or "Unknown")

        self.console.print(Panel(details_table, title="[bold]Details[/bold]", border_style="blue"))
        self.console.input(f"\n{self.msg('press_enter')}")

    def install_mod(self):
        """Installiert oder aktualisiert den Mod"""
        self.clear_screen()
        self.show_header()

        if not self.game_folder:
            self.console.print(Panel(
                f"[bold red]{self.msg('game_not_found')}[/bold red]",
                border_style="red"
            ))
            self.console.input(f"\n{self.msg('press_enter')}")
            return

        # Schritte erstellen
        steps = [
            InstallationStep(self.msg('step_find_game'), 'step_find_game'),
            InstallationStep(self.msg('step_create_mods'), 'step_create_mods'),
            InstallationStep(self.msg('step_backup'), 'step_backup'),
            InstallationStep(self.msg('step_download'), 'step_download'),
            InstallationStep(self.msg('step_install'), 'step_install'),
            InstallationStep(self.msg('step_cleanup'), 'step_cleanup'),
        ]

        self.installation_cancelled = False
        tmp_file_path = None
        current_step = 0

        try:
            mods_folder = self.game_folder / MODS_DIR_NAME
            target_file_path = mods_folder / FILE_NAME

            with Live(self.create_steps_panel(steps), refresh_per_second=4, console=self.console) as live:

                # Schritt 1
                steps[current_step].start()
                live.update(self.create_steps_panel(steps))
                time.sleep(0.3)
                steps[current_step].complete()
                live.update(self.create_steps_panel(steps))
                current_step += 1

                # Schritt 2
                steps[current_step].start()
                live.update(self.create_steps_panel(steps))
                mods_folder.mkdir(exist_ok=True)
                time.sleep(0.3)
                steps[current_step].complete()
                live.update(self.create_steps_panel(steps))
                current_step += 1

                # Schritt 3
                if target_file_path.exists():
                    steps[current_step].start()
                    live.update(self.create_steps_panel(steps))
                    backup_name = f"{FILE_NAME}.backup.{int(time.time())}"
                    self.backup_file_path = mods_folder / backup_name
                    shutil.copy2(target_file_path, self.backup_file_path)
                    time.sleep(0.5)
                    steps[current_step].complete()
                else:
                    steps[current_step].status = "completed"
                live.update(self.create_steps_panel(steps))
                current_step += 1

                # Schritt 4
                steps[current_step].start()
                live.update(self.create_steps_panel(steps))

            # Download
            self.console.print()
            download_successful = False

            for attempt, url in enumerate([DOWNLOAD_URL, MIRROR_URL], 1):
                try:
                    if attempt == 2:
                        self.console.print("[yellow]Versuche alternativen Server...[/yellow]")

                    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                        tmp_file_path = tmp_file.name

                        with requests.get(url, stream=True, allow_redirects=True, timeout=DOWNLOAD_TIMEOUT) as r:
                            r.raise_for_status()
                            total_size = int(r.headers.get('content-length', 0))

                            with Progress(
                                SpinnerColumn(),
                                TextColumn("[bold blue]{task.description}"),
                                BarColumn(complete_style="green", finished_style="bold green", bar_width=40),
                                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                                TextColumn("•"),
                                DownloadColumn(),
                                TextColumn("•"),
                                TransferSpeedColumn(),
                                TextColumn("•"),
                                TimeRemainingColumn(),
                                console=self.console,
                            ) as progress:

                                task = progress.add_task(
                                    f"Download ({self.format_size(total_size)})",
                                    total=total_size
                                )

                                for chunk in r.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                                    if self.installation_cancelled:
                                        raise KeyboardInterrupt()

                                    if chunk:
                                        tmp_file.write(chunk)
                                        progress.update(task, advance=len(chunk))

                    download_successful = True
                    steps[current_step].complete()
                    current_step += 1
                    break

                except requests.RequestException as e:
                    if tmp_file_path and os.path.exists(tmp_file_path):
                        try:
                            os.remove(tmp_file_path)
                        except OSError:
                            pass
                        tmp_file_path = None

                    if attempt == 2:
                        steps[current_step].fail(f"Download fehlgeschlagen")
                        raise Exception(f"Download von beiden Servern fehlgeschlagen: {e}")

            if not download_successful:
                steps[current_step].fail("Download konnte nicht abgeschlossen werden")
                raise Exception("Download konnte nicht abgeschlossen werden")

            self.console.print()

            # Restliche Schritte
            with Live(self.create_steps_panel(steps), refresh_per_second=4, console=self.console) as live:

                # Schritt 5
                steps[current_step].start()
                live.update(self.create_steps_panel(steps))
                shutil.move(tmp_file_path, target_file_path)
                tmp_file_path = None
                time.sleep(0.5)
                steps[current_step].complete()
                live.update(self.create_steps_panel(steps))
                current_step += 1

                # Schritt 6
                steps[current_step].start()
                live.update(self.create_steps_panel(steps))

                if self.backup_file_path and self.backup_file_path.exists():
                    self.backup_file_path.unlink()
                    self.backup_file_path = None

                latest_version = self.scrape_website_version() or "Unknown"
                status_file_path = self.get_status_file_path(mods_folder)
                with open(status_file_path, 'w', encoding='utf-8') as f:
                    json.dump({"installed_version": latest_version}, f, indent=2)

                time.sleep(0.5)
                steps[current_step].complete()
                live.update(self.create_steps_panel(steps))

            self.console.print()

            total_time = sum(step.get_duration() or 0 for step in steps)

            success_text = f"[bold green]{ICON_SUCCESS} {self.msg('success_title')}[/bold green]\n\n"
            success_text += self.msg('success_message')
            success_text += f"\n\n[dim]{self.msg('installation_time')}: {self.format_time(total_time)}[/dim]"

            self.console.print(Panel(
                success_text,
                border_style="green",
                box=box.DOUBLE
            ))

            # Update lokalen Status
            self.mod_installed = True
            self.local_version = latest_version

        except KeyboardInterrupt:
            self.console.print("\n[yellow]Installation abgebrochen...[/yellow]")
            if self.backup_file_path and self.backup_file_path.exists():
                try:
                    original_path = self.backup_file_path.parent / FILE_NAME
                    shutil.move(self.backup_file_path, original_path)
                    self.console.print(f"[green]{ICON_SUCCESS} Backup wiederhergestellt[/green]")
                except Exception as e:
                    self.console.print(f"[red]{ICON_ERROR} Fehler: {e}[/red]")

        except Exception as e:
            self.console.print()
            self.console.print(Panel(
                f"[bold red]{ICON_ERROR} {self.msg('error_title')}[/bold red]\n\n{str(e)}",
                border_style="red"
            ))

            if self.backup_file_path and self.backup_file_path.exists():
                try:
                    original_path = self.backup_file_path.parent / FILE_NAME
                    shutil.move(self.backup_file_path, original_path)
                    self.console.print(f"[green]{ICON_SUCCESS} Backup wiederhergestellt[/green]")
                except Exception:
                    pass

        finally:
            if tmp_file_path and os.path.exists(tmp_file_path):
                try:
                    os.remove(tmp_file_path)
                except OSError:
                    pass

        self.console.input(f"\n{self.msg('press_enter')}")

    def select_folder_manually(self):
        """Manuelle Ordnerauswahl"""
        self.console.print("[yellow]Bitte gib den vollstaendigen Pfad zum Spielordner ein:[/yellow]")
        example_path = Path.home() / 'Documents' / 'My Games' / GAME_DIR_NAME
        self.console.print(f"[dim]Beispiel: {example_path}[/dim]\n")

        folder_path = Prompt.ask("[cyan]Pfad")

        try:
            path = Path(folder_path)
            if not path.exists():
                self.console.print(f"[red]{ICON_ERROR} Pfad existiert nicht![/red]")
            elif path.name != GAME_DIR_NAME:
                self.console.print(f"[red]{ICON_ERROR} Falscher Ordnername! Erwartet: {GAME_DIR_NAME}[/red]")
            else:
                self.selected_game_folder = path
                self.game_folder = path
                self.console.print(f"[green]{ICON_SUCCESS} Spielordner gesetzt[/green]")
                # Status neu pruefen
                self.check_status_silent()
        except Exception as e:
            self.console.print(f"[red]{ICON_ERROR} Fehler: {e}[/red]")

        time.sleep(2)

    def launch_game(self):
        """Startet das Spiel"""
        with self.console.status("[bold green]Starte Spiel...[/bold green]", spinner="dots"):
            try:
                if os.name == 'nt':
                    subprocess.run(['start', 'steam://run/2707070'], shell=True, check=False)
                else:
                    subprocess.run(['xdg-open', 'steam://run/2707070'], check=False)
                time.sleep(2)
            except Exception as e:
                self.console.print(f"[red]Fehler: {e}[/red]")
                time.sleep(2)
                return

        self.console.print(f"[green]{ICON_SUCCESS} Spiel wird gestartet...[/green]")
        time.sleep(2)

    def load_settings(self):
        try:
            settings_file = Path("installer_settings.json")
            if settings_file.exists():
                with open(settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception:
            pass

        return {"language": "de"}

    def save_settings(self):
        try:
            with open("installer_settings.json", 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def run(self):
        """Hauptschleife"""
        while True:
            try:
                self.show_startup_screen()
                choice, menu_items = self.show_main_menu()

                # Finde die Aktion
                action = None
                for option, key in menu_items:
                    if option == choice:
                        action = key
                        break

                if action == "exit":
                    self.clear_screen()
                    self.console.print(Panel(
                        "[bold cyan]Vielen Dank!\n[dim]Viel Spass mit der U-Bahn Berlin![/dim][/bold cyan]",
                        border_style="cyan",
                        box=box.DOUBLE
                    ))
                    break
                elif action in ["install_mod", "update_mod", "reinstall_mod"]:
                    self.install_mod()
                elif action == "launch_game":
                    self.launch_game()
                elif action == "advanced_options":
                    self.show_advanced_menu()
                elif action == "manual_path":
                    self.select_folder_manually()

            except KeyboardInterrupt:
                self.console.print("\n\n[yellow]Programm wird beendet...[/yellow]")
                break
            except Exception as e:
                self.console.print(f"\n[red]Fehler: {e}[/red]")
                self.console.input(f"\n{self.msg('press_enter')}")


if __name__ == '__main__':
    installer = TerminalInstaller()
    installer.run()
