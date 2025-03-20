import subprocess
import threading
import logging
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime, timedelta
import time
import platform
import os
import sys
import webbrowser


class TextHandler(logging.Handler):
    """Klasa przechwytująca logi i przekierowująca je do widgetu Text."""

    def __init__(self, text_widget):
        logging.Handler.__init__(self)
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)

        def append():
            self.text_widget.configure(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)  # Przewijanie do końca
            self.text_widget.configure(state='disabled')

        # Uruchamianie w głównym wątku Tkinter
        self.text_widget.after(0, append)


class TimeSyncApp:
    def __init__(self, root):
        self.root = root
        self.root.title("ZegarSync - Aplikacja zegara systemowego")
        self.root.geometry("700x650")
        self.root.resizable(True, True)

        # Ustawienie minimalnego rozmiaru okna
        self.root.minsize(600, 550)

        # Zmienne
        self.ntp_server = tk.StringVar(value="tempus1.gum.gov.pl")
        self.is_syncing = False
        self.sync_thread = None

        # Tryb testowy
        self.test_mode = tk.BooleanVar(value=False)

        # Zmienna dla wirtualnego czasu
        self.virtual_time_offset = 0  # Offset w sekundach

        # Utworzenie i skonfigurowanie widżetów
        self.create_widgets()
        self.setup_logging()

        # Sprawdzenie uprawnień administratora przy starcie
        self.is_admin_mode = self.is_admin()
        if not self.is_admin_mode:
            logging.warning("Aplikacja nie została uruchomiona z uprawnieniami administratora.")
            logging.info("Synchronizacja czasu systemowego będzie niedostępna.")
            logging.info("Dostępna jest praca z czasem wirtualnym (bez modyfikacji czasu systemowego).")

    def create_widgets(self):
        """Tworzenie elementów interfejsu."""
        # Główny kontener
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Zakładki
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Zakładka 1: Podstawowe zegary
        basic_frame = ttk.Frame(notebook, padding="10")
        notebook.add(basic_frame, text="Zegary")

        # Zakładka 2: Zaawansowana synchronizacja
        sync_frame = ttk.Frame(notebook, padding="10")
        notebook.add(sync_frame, text="Synchronizacja")

        # === ZAKŁADKA 1: ZEGARY ===
        # Rama z zegarami
        clocks_frame = ttk.LabelFrame(basic_frame, text="Zegary", padding="10")
        clocks_frame.pack(fill=tk.X, padx=5, pady=5)

        # Styl dla zegarów - czarny tekst
        style = ttk.Style()
        style.configure('Clock.TLabel', font=('Arial', 24, 'bold'), background='white', foreground='black')
        style.configure('VirtualClock.TLabel', font=('Arial', 24, 'bold'), background='lightblue', foreground='black')

        # Kontener dla 3 zegarów w rzędzie
        clock_container = ttk.Frame(clocks_frame)
        clock_container.pack(fill=tk.X)

        # 1. Zegar lokalny (systemowy)
        local_clock_frame = ttk.LabelFrame(clock_container, text="Czas systemowy", padding="5")
        local_clock_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.local_date_label = ttk.Label(local_clock_frame, font=('Arial', 12))
        self.local_date_label.pack(fill=tk.X)

        self.local_time_label = ttk.Label(local_clock_frame, style='Clock.TLabel')
        self.local_time_label.pack(fill=tk.X, pady=5)

        # 2. Zegar UTC
        utc_clock_frame = ttk.LabelFrame(clock_container, text="Czas UTC", padding="5")
        utc_clock_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.utc_date_label = ttk.Label(utc_clock_frame, font=('Arial', 12))
        self.utc_date_label.pack(fill=tk.X)

        self.utc_time_label = ttk.Label(utc_clock_frame, style='Clock.TLabel')
        self.utc_time_label.pack(fill=tk.X, pady=5)

        # 3. Zegar wirtualny
        virtual_clock_frame = ttk.LabelFrame(clock_container, text="Czas wirtualny", padding="5")
        virtual_clock_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        self.virtual_date_label = ttk.Label(virtual_clock_frame, font=('Arial', 12))
        self.virtual_date_label.pack(fill=tk.X)

        self.virtual_time_label = ttk.Label(virtual_clock_frame, style='VirtualClock.TLabel')
        self.virtual_time_label.pack(fill=tk.X, pady=5)

        # Rama z kontrolą czasu wirtualnego
        virtual_control_frame = ttk.LabelFrame(basic_frame, text="Zarządzanie czasem wirtualnym", padding="10")
        virtual_control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Przyciski do regulacji czasu wirtualnego
        adjust_frame = ttk.Frame(virtual_control_frame)
        adjust_frame.pack(fill=tk.X, pady=5)

        # Przyciski po lewej
        left_buttons = ttk.Frame(adjust_frame)
        left_buttons.pack(side=tk.LEFT, padx=5)

        ttk.Button(left_buttons, text="-1 godzina", command=lambda: self.adjust_virtual_time(-3600)).pack(side=tk.LEFT,
                                                                                                          padx=2)
        ttk.Button(left_buttons, text="-10 minut", command=lambda: self.adjust_virtual_time(-600)).pack(side=tk.LEFT,
                                                                                                        padx=2)
        ttk.Button(left_buttons, text="-1 minuta", command=lambda: self.adjust_virtual_time(-60)).pack(side=tk.LEFT,
                                                                                                       padx=2)

        # Przyciski po prawej
        right_buttons = ttk.Frame(adjust_frame)
        right_buttons.pack(side=tk.RIGHT, padx=5)

        ttk.Button(right_buttons, text="+1 minuta", command=lambda: self.adjust_virtual_time(60)).pack(side=tk.LEFT,
                                                                                                       padx=2)
        ttk.Button(right_buttons, text="+10 minut", command=lambda: self.adjust_virtual_time(600)).pack(side=tk.LEFT,
                                                                                                        padx=2)
        ttk.Button(right_buttons, text="+1 godzina", command=lambda: self.adjust_virtual_time(3600)).pack(side=tk.LEFT,
                                                                                                          padx=2)

        # Przyciski zarządzania
        manage_frame = ttk.Frame(virtual_control_frame)
        manage_frame.pack(fill=tk.X, pady=5)

        ttk.Button(manage_frame, text="Resetuj zegar wirtualny",
                   command=self.reset_virtual_time).pack(side=tk.LEFT, expand=True)

        ttk.Button(manage_frame, text="Zapisz ustawienie",
                   command=self.save_time_settings).pack(side=tk.LEFT, expand=True)

        ttk.Button(manage_frame, text="Wczytaj ustawienie",
                   command=self.load_time_settings).pack(side=tk.LEFT, expand=True)

        # === ZAKŁADKA 2: SYNCHRONIZACJA ===
        sync_label = ttk.Label(sync_frame, text="Synchronizacja czasu systemowego z serwerem NTP",
                               font=("Arial", 12, "bold"))
        sync_label.pack(pady=10)

        # Informacja o uprawnieniach
        admin_frame = ttk.Frame(sync_frame)
        admin_frame.pack(fill=tk.X, pady=5)

        self.admin_icon = ttk.Label(admin_frame, text="⚠️", font=("Arial", 16))
        self.admin_icon.pack(side=tk.LEFT, padx=5)

        admin_text = "Ta funkcja wymaga uruchomienia aplikacji z uprawnieniami administratora."
        self.admin_label = ttk.Label(admin_frame, text=admin_text, font=("Arial", 10))
        self.admin_label.pack(side=tk.LEFT, padx=5)

        ttk.Separator(sync_frame, orient='horizontal').pack(fill=tk.X, pady=10)

        # Ustawienia serwera NTP
        ntp_frame = ttk.LabelFrame(sync_frame, text="Serwer NTP", padding="10")
        ntp_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(ntp_frame, text="Adres serwera NTP:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.server_entry = ttk.Entry(ntp_frame, width=40, textvariable=self.ntp_server)
        self.server_entry.grid(row=0, column=1, sticky=tk.W + tk.E, padx=5, pady=5)

        # Lista popularnych serwerów
        ttk.Label(ntp_frame, text="Popularne serwery:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)

        server_frame = ttk.Frame(ntp_frame)
        server_frame.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)

        for server in ["tempus1.gum.gov.pl", "time.windows.com", "pool.ntp.org"]:
            btn = ttk.Button(server_frame, text=server,
                             command=lambda s=server: self.ntp_server.set(s))
            btn.pack(side=tk.LEFT, padx=5)

        # Opcje synchronizacji
        options_frame = ttk.LabelFrame(sync_frame, text="Opcje synchronizacji", padding="10")
        options_frame.pack(fill=tk.X, padx=5, pady=5)

        # Checkbox dla trybu testowego
        self.test_mode_cb = ttk.Checkbutton(options_frame, text="Tryb testowy (bez synchronizacji)",
                                            variable=self.test_mode)
        self.test_mode_cb.pack(anchor=tk.W, pady=5)

        # Przycisk synchronizacji
        sync_button_frame = ttk.Frame(options_frame)
        sync_button_frame.pack(fill=tk.X, pady=10)

        self.sync_button = ttk.Button(sync_button_frame, text="Synchronizuj czas z serwerem NTP",
                                      command=self.start_sync, width=30)
        self.sync_button.pack(pady=5)

        # Pasek postępu
        self.progress = ttk.Progressbar(options_frame, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=5)

        # Informacje o usłudze Windows Time
        service_frame = ttk.LabelFrame(sync_frame, text="Status usługi Windows Time", padding="10")
        service_frame.pack(fill=tk.X, padx=5, pady=5)

        service_buttons = ttk.Frame(service_frame)
        service_buttons.pack(fill=tk.X)

        ttk.Button(service_buttons, text="Sprawdź status usługi",
                   command=self.check_time_service).pack(side=tk.LEFT, expand=True, padx=5, pady=5)

        ttk.Button(service_buttons, text="Uruchom usługę",
                   command=lambda: self.manage_time_service("start")).pack(side=tk.LEFT, expand=True, padx=5, pady=5)

        ttk.Button(service_buttons, text="Zatrzymaj usługę",
                   command=lambda: self.manage_time_service("stop")).pack(side=tk.LEFT, expand=True, padx=5, pady=5)

        # WSPÓLNE ELEMENTY DLA OBU ZAKŁADEK
        # Okno logów
        log_frame = ttk.LabelFrame(main_frame, text="Logi", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled', height=8)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Status systemu operacyjnego i GitHub link (nowa ramka)
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # Informacja o systemie (lewa strona)
        self.system_label = ttk.Label(status_frame, text=f"System: {platform.system()} {platform.release()}")
        self.system_label.pack(side=tk.LEFT)

        # Link do repozytorium GitHub (prawa strona)
        self.github_link = ttk.Label(status_frame, text="GitHub",
                                     foreground="blue", cursor="hand2")
        self.github_link.pack(side=tk.RIGHT, padx=10)
        self.github_link.bind("<Button-1>", self.open_github)

        # Etykieta autora, która wyświetli popup po kliknięciu
        self.author_label = ttk.Label(status_frame, text="Autor", foreground="blue", cursor="hand2")
        self.author_label.pack(side=tk.RIGHT)
        self.author_label.bind("<Button-1>", self.show_author)

        # Uruchomienie aktualizacji zegarów
        self.update_clocks()

        # Aktualizacja stanu przycisków w zależności od uprawnień
        self.update_admin_status()

    def update_admin_status(self):
        """Aktualizuje interfejs na podstawie uprawnień administratora."""
        if self.is_admin():
            self.admin_icon.config(text="✅")
            self.admin_label.config(text="Aplikacja uruchomiona z uprawnieniami administratora.")
            self.sync_button.config(state=tk.NORMAL)
        else:
            self.admin_icon.config(text="⚠️")
            self.admin_label.config(text="Wymagane uprawnienia administratora! Funkcje synchronizacji niedostępne.")
            self.sync_button.config(state=tk.DISABLED)

    def open_github(self, event):
        """Otwiera repozytorium GitHub w przeglądarce."""
        webbrowser.open_new("https://github.com/dkoryto/time_sync")

    def show_author(self, event):
        """Wyświetla popup z informacją o autorze."""
        messagebox.showinfo("Autor",
                            "Dariusz Koryto\nE-mail: dariusz@koryto.eu\n\nAplikacja do synchronizacji czasu\nLicencja: MIT")

    def update_clocks(self):
        """Aktualizacja wyświetlania zegarów co sekundę."""
        # Pobranie aktualnego czasu lokalnego
        now_local = datetime.now()
        local_date = now_local.strftime("%Y-%m-%d")
        local_time = now_local.strftime("%H:%M:%S")

        # Pobranie aktualnego czasu UTC
        now_utc = datetime.utcnow()
        utc_date = now_utc.strftime("%Y-%m-%d")
        utc_time = now_utc.strftime("%H:%M:%S")

        # Obliczenie czasu wirtualnego
        virtual_time = now_local + timedelta(seconds=self.virtual_time_offset)
        virtual_date = virtual_time.strftime("%Y-%m-%d")
        virtual_time_str = virtual_time.strftime("%H:%M:%S")

        # Aktualizacja etykiet
        self.local_date_label.config(text=f"Data: {local_date}")
        self.local_time_label.config(text=f"{local_time}")

        self.utc_date_label.config(text=f"Data: {utc_date}")
        self.utc_time_label.config(text=f"{utc_time}")

        self.virtual_date_label.config(text=f"Data: {virtual_date}")
        self.virtual_time_label.config(text=f"{virtual_time_str}")

        # Wywołanie funkcji ponownie po 1000ms (1 sekunda)
        self.root.after(1000, self.update_clocks)

    def setup_logging(self):
        """Konfiguracja logowania do okna tekstowego."""
        # Konfiguracja loggera
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Usuwanie istniejących handlerów, aby uniknąć duplikacji logów
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Handler do przekierowania logów do widgetu Text
        text_handler = TextHandler(self.log_area)
        text_handler.setLevel(logging.INFO)
        text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(text_handler)

        # Handler do pliku logów
        log_filename = 'timesync_gui.log'
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        root_logger.addHandler(file_handler)

        # Log początkowy
        logging.info(f"Uruchomiono aplikację na Windows {platform.win32_ver()[0]}")

    def is_admin(self):
        """Sprawdza, czy aplikacja jest uruchomiona z uprawnieniami administratora."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False

    def adjust_virtual_time(self, seconds):
        """Dostosowuje wirtualny czas o podaną liczbę sekund."""
        self.virtual_time_offset += seconds
        offset_str = self.format_time_offset(self.virtual_time_offset)
        logging.info(f"Zmieniono czas wirtualny o {seconds} sekund. Obecny offset: {offset_str}")

    def format_time_offset(self, seconds):
        """Formatuje offset czasu do czytelnej postaci."""
        sign = "+" if seconds >= 0 else "-"
        abs_seconds = abs(seconds)
        hours = abs_seconds // 3600
        minutes = (abs_seconds % 3600) // 60
        secs = abs_seconds % 60

        return f"{sign}{hours:02d}:{minutes:02d}:{secs:02d}"

    def reset_virtual_time(self):
        """Resetuje wirtualny czas do czasu systemowego."""
        self.virtual_time_offset = 0
        logging.info("Zresetowano zegar wirtualny do czasu systemowego")

    def save_time_settings(self):
        """Zapisuje obecne ustawienie czasu do pliku."""
        try:
            with open("time_settings.txt", "w") as file:
                file.write(str(self.virtual_time_offset))
            offset_str = self.format_time_offset(self.virtual_time_offset)
            logging.info(f"Zapisano ustawienia czasu wirtualnego (offset: {offset_str})")
            messagebox.showinfo("Zapisano", "Ustawienia czasu zostały zapisane")
        except Exception as e:
            logging.error(f"Błąd podczas zapisywania ustawień: {str(e)}")
            messagebox.showerror("Błąd", f"Nie udało się zapisać ustawień: {str(e)}")

    def load_time_settings(self):
        """Wczytuje ustawienie czasu z pliku."""
        try:
            if os.path.exists("time_settings.txt"):
                with open("time_settings.txt", "r") as file:
                    self.virtual_time_offset = int(file.read().strip())

                offset_str = self.format_time_offset(self.virtual_time_offset)
                logging.info(f"Wczytano ustawienia czasu wirtualnego (offset: {offset_str})")
                messagebox.showinfo("Wczytano", f"Ustawienia czasu zostały wczytane\nOffset: {offset_str}")
            else:
                logging.warning("Nie znaleziono zapisanych ustawień czasu")
                messagebox.showwarning("Brak pliku", "Nie znaleziono zapisanych ustawień czasu")
        except Exception as e:
            logging.error(f"Błąd podczas wczytywania ustawień: {str(e)}")
            messagebox.showerror("Błąd", f"Nie udało się wczytać ustawień: {str(e)}")

    def check_time_service(self):
        """Sprawdza stan usługi Windows Time i wyświetla informacje."""
        if not self.is_admin():
            logging.warning("Sprawdzenie stanu usługi wymaga uprawnień administratora.")
            messagebox.showwarning("Brak uprawnień",
                                   "Sprawdzenie stanu usługi Windows Time wymaga uprawnień administratora.")
            return

        try:
            # Sprawdź status usługi
            result = subprocess.run("sc query w32time", shell=True, capture_output=True, text=True)

            # Sprawdź źródło czasu
            source_result = subprocess.run("w32tm /query /source", shell=True, capture_output=True, text=True)

            # Sprawdź konfigurację
            config_result = subprocess.run("w32tm /query /configuration", shell=True,
                                           capture_output=True, text=True)

            # Wyświetl informacje w logu
            logging.info(f"Status usługi Windows Time:")

            if "RUNNING" in result.stdout:
                logging.info("- Stan usługi: URUCHOMIONA")
            elif "STOPPED" in result.stdout:
                logging.info("- Stan usługi: ZATRZYMANA")
            elif "DISABLED" in result.stdout:
                logging.info("- Stan usługi: WYŁĄCZONA")
            else:
                logging.info("- Stan usługi: NIEZNANY")

            if source_result.returncode == 0:
                logging.info(f"- Źródło czasu: {source_result.stdout.strip()}")
            else:
                logging.info("- Nie można określić źródła czasu.")

            # Pokaż szczegółową informację w oknie dialogowym
            info = f"Status usługi Windows Time:\n\n"

            if "RUNNING" in result.stdout:
                info += "Stan usługi: URUCHOMIONA\n"
            elif "STOPPED" in result.stdout:
                info += "Stan usługi: ZATRZYMANA\n"
            elif "DISABLED" in result.stdout:
                info += "Stan usługi: WYŁĄCZONA\n"
            else:
                info += "Stan usługi: NIEZNANY\n"

            if source_result.returncode == 0:
                info += f"Źródło czasu: {source_result.stdout.strip()}\n\n"
            else:
                info += "Nie można określić źródła czasu.\n\n"

            # Dodajemy wybrane fragmenty konfiguracji
            info += "Fragmenty konfiguracji:\n"
            config_lines = config_result.stdout.splitlines()
            important_keys = ["Type", "NtpServer", "TimeProviders"]

            for line in config_lines:
                for key in important_keys:
                    if key in line:
                        info += f"{line.strip()}\n"

            messagebox.showinfo("Status usługi Windows Time", info)

        except Exception as e:
            logging.error(f"Błąd podczas sprawdzania stanu usługi: {str(e)}")
            messagebox.showerror("Błąd", f"Nie udało się sprawdzić stanu usługi: {str(e)}")

    def manage_time_service(self, action):
        """Zarządza usługą Windows Time (start/stop)."""
        if not self.is_admin():
            logging.warning(f"Zarządzanie usługą wymaga uprawnień administratora.")
            messagebox.showwarning("Brak uprawnień",
                                   "Zarządzanie usługą Windows Time wymaga uprawnień administratora.")
            return

        try:
            if action == "start":
                # Najpierw włącz usługę, jeśli jest wyłączona
                subprocess.run("sc config w32time start= auto", shell=True, check=True)
                logging.info("Ustawiono automatyczne uruchamianie usługi Windows Time.")

                # Uruchom usługę
                result = subprocess.run("net start w32time", shell=True, capture_output=True, text=True)

                if result.returncode == 0:
                    logging.info("Usługa Windows Time została uruchomiona.")
                    messagebox.showinfo("Sukces", "Usługa Windows Time została uruchomiona.")
                else:
                    logging.error(f"Nie udało się uruchomić usługi: {result.stderr}")
                    messagebox.showerror("Błąd", f"Nie udało się uruchomić usługi Windows Time:\n{result.stderr}")

            elif action == "stop":
                result = subprocess.run("net stop w32time", shell=True, capture_output=True, text=True)

                if result.returncode == 0:
                    logging.info("Usługa Windows Time została zatrzymana.")
                    messagebox.showinfo("Sukces", "Usługa Windows Time została zatrzymana.")
                else:
                    logging.error(f"Nie udało się zatrzymać usługi: {result.stderr}")
                    messagebox.showerror("Błąd", f"Nie udało się zatrzymać usługi Windows Time:\n{result.stderr}")

        except Exception as e:
            logging.error(f"Błąd podczas zarządzania usługą: {str(e)}")
            messagebox.showerror("Błąd", f"Wystąpił błąd: {str(e)}")

    def start_sync(self):
        """Rozpoczyna proces synchronizacji w osobnym wątku."""
        if not self.is_admin():
            logging.error("Synchronizacja czasu wymaga uprawnień administratora.")
            messagebox.showerror("Brak uprawnień",
                                 "Synchronizacja czasu systemowego wymaga uprawnień administratora.\n"
                                 "Uruchom aplikację jako administrator.")
            return

        # W trybie testowym tylko symulujemy synchronizację
        if self.test_mode.get():
            logging.info("Uruchomiono w trybie testowym - synchronizacja jest symulowana")
            self.simulate_sync()
            return

        if self.is_syncing:
            messagebox.showinfo("Synchronizacja w toku", "Proces synchronizacji już trwa.")
            return

        self.is_syncing = True
        self.sync_button.config(state=tk.DISABLED)
        self.progress.start(10)

        # Uruchomienie synchronizacji w osobnym wątku
        self.sync_thread = threading.Thread(target=self.sync_time)
        self.sync_thread.daemon = True
        self.sync_thread.start()

    def simulate_sync(self):
        """Symuluje proces synchronizacji (do celów testowych)."""
        self.is_syncing = True
        self.sync_button.config(state=tk.DISABLED)
        self.progress.start(10)

        def simulate_process():
            try:
                server = self.ntp_server.get()
                logging.info(f"[SYMULACJA] Rozpoczęcie synchronizacji z serwerem: {server}")

                # Symulacja etapów synchronizacji
                logging.info("[SYMULACJA] Etap 1/5: Sprawdzanie stanu usługi czasu...")
                time.sleep(1)

                logging.info("[SYMULACJA] Etap 2/5: Włączanie usługi czasu...")
                time.sleep(1)

                logging.info("[SYMULACJA] Etap 3/5: Konfiguracja serwera czasu...")
                time.sleep(1.5)

                logging.info("[SYMULACJA] Etap 4/5: Uruchamianie usługi czasu...")
                time.sleep(1)

                logging.info("[SYMULACJA] Etap 5/5: Wymuszanie resynchronizacji...")
                time.sleep(2)

                logging.info("[SYMULACJA] Synchronizacja zakończona pomyślnie!")
                logging.info(f"[SYMULACJA] Obecny czas: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            except Exception as e:
                logging.error(f"[SYMULACJA] Błąd: {str(e)}")
            finally:
                self.root.after(0, self.finish_sync)

        # Uruchomienie symulacji w osobnym wątku
        sim_thread = threading.Thread(target=simulate_process)
        sim_thread.daemon = True
        sim_thread.start()

    def check_service_status(self):
        """Sprawdza status usługi Windows Time."""
        result = subprocess.run("sc query w32time", shell=True, capture_output=True, text=True)
        if "RUNNING" in result.stdout:
            return "running"
        elif "STOPPED" in result.stdout:
            return "stopped"
        elif "DISABLED" in result.stdout:
            return "disabled"
        else:
            return "unknown"

    def enable_time_service(self):
        """Włącza usługę Windows Time jeśli jest wyłączona."""
        logging.info("Włączanie usługi Windows Time...")
        result = subprocess.run("sc config w32time start= auto", shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Nie udało się włączyć usługi Windows Time: {result.stderr}")
            return False
        else:
            logging.info("Usługa Windows Time została włączona.")
            return True

    def sync_time(self):
        """Synchronizuje zegar systemowy z serwerem NTP."""
        try:
            server = self.ntp_server.get()
            logging.info(f"Rozpoczęcie synchronizacji z serwerem: {server}")

            # Etap 1: Sprawdzenie stanu usługi
            logging.info("Etap 1/5: Sprawdzanie stanu usługi Windows Time...")
            service_status = self.check_service_status()
            logging.info(f"Status usługi Windows Time: {service_status}")

            # Etap 2: Włączenie usługi jeśli jest wyłączona
            if service_status == "disabled":
                logging.info("Etap 2/5: Włączanie usługi Windows Time...")
                if not self.enable_time_service():
                    logging.error("Nie można kontynuować bez włączenia usługi Windows Time.")
                    return
            else:
                logging.info("Etap 2/5: Usługa Windows Time jest już włączona.")

            # Etap 3: Zatrzymanie usługi (jeśli jest uruchomiona)
            logging.info("Etap 3/5: Zatrzymywanie usługi Windows Time...")
            if service_status == "running":
                result = subprocess.run("net stop w32time", shell=True, capture_output=True, text=True)
                if result.returncode != 0 and "nie jest uruchomiona" not in result.stderr:
                    logging.warning(f"Ostrzeżenie przy zatrzymywaniu usługi: {result.stderr}")
                else:
                    logging.info("Usługa Windows Time zatrzymana pomyślnie.")
            else:
                logging.info("Usługa Windows Time już była zatrzymana.")

            # Etap 4: Konfiguracja serwera czasu
            logging.info("Etap 4/5: Konfiguracja serwera czasu...")
            config_cmd = f'w32tm /config /manualpeerlist:"{server}" /syncfromflags:manual /reliable:yes /update'
            result = subprocess.run(config_cmd, shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Błąd przy konfiguracji serwera czasu: {result.stderr}")
            else:
                logging.info("Serwer czasu skonfigurowany pomyślnie.")

            # Etap 5: Uruchomienie usługi
            logging.info("Etap 5/5: Uruchamianie usługi Windows Time...")
            result = subprocess.run("net start w32time", shell=True, capture_output=True, text=True)
            if result.returncode != 0:
                logging.error(f"Błąd przy uruchamianiu usługi: {result.stderr}")
                # Spróbuj alternatywną metodę uruchomienia
                logging.info("Próba alternatywnej metody uruchomienia usługi...")
                result = subprocess.run("sc start w32time", shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    logging.error(f"Nie udało się uruchomić usługi alternatywną metodą: {result.stderr}")
                else:
                    logging.info("Usługa Windows Time uruchomiona alternatywną metodą.")
            else:
                logging.info("Usługa Windows Time uruchomiona pomyślnie.")

            # Wymuszenie resynchronizacji
            logging.info("Wymuszanie resynchronizacji...")
            time.sleep(2)  # Dajemy usłudze czas na stabilizację
            result = subprocess.run("w32tm /resync /force", shell=True, capture_output=True, text=True)
            output = result.stdout + result.stderr

            if "successfully synchronized" in output.lower() or "the command completed successfully" in output.lower():
                logging.info("Synchronizacja zakończona pomyślnie!")
                messagebox.showinfo("Sukces", f"Czas został zsynchronizowany z serwerem {server}")
            else:
                logging.warning(f"Synchronizacja mogła się nie powieść: {output}")

                # Spróbuj ponownie po krótkiej przerwie
                logging.info("Próba ponownej synchronizacji po 5 sekundach...")
                time.sleep(5)
                result = subprocess.run("w32tm /resync /force", shell=True, capture_output=True, text=True)
                output = result.stdout + result.stderr

                if "successfully synchronized" in output.lower() or "the command completed successfully" in output.lower():
                    logging.info("Druga próba synchronizacji zakończona pomyślnie!")
                    messagebox.showinfo("Sukces", f"Czas został zsynchronizowany z serwerem {server} (druga próba)")
                else:
                    logging.warning(f"Druga próba synchronizacji nie powiodła się: {output}")
                    messagebox.showwarning("Ostrzeżenie",
                                           "Synchronizacja mogła się nie powieść. Sprawdź logi dla szczegółów.")

            logging.info(f"Aktualny czas systemowy: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        except Exception as e:
            logging.error(f"Wystąpił błąd podczas synchronizacji: {str(e)}")
            messagebox.showerror("Błąd", f"Wystąpił błąd podczas synchronizacji:\n{str(e)}")
        finally:
            # Zakończenie procesu synchronizacji (w głównym wątku GUI)
            self.root.after(0, self.finish_sync)

    def finish_sync(self):
        """Kończy proces synchronizacji i aktualizuje UI."""
        self.progress.stop()
        self.sync_button.config(state=tk.NORMAL)
        self.is_syncing = False


def main():
    """Funkcja główna aplikacji."""
    root = tk.Tk()
    app = TimeSyncApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()