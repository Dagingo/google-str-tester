# finance_tool/gui.py

import customtkinter as ctk
from tkinter import ttk, messagebox # filedialog nicht direkt verwendet, kann raus
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import datetime
import logging # Logging hinzugefügt

# Importiere Module aus dem Paket finance_tool
try:
    from .data_fetcher import fetch_data, get_stock_info
    from .strategies import setup_strategy
    from .backtester import Backtester
except ImportError:
    print("Versuche Fallback-Importe für GUI (wahrscheinlich direkter Testlauf von gui.py)...")
    from data_fetcher import fetch_data, get_stock_info
    from strategies import setup_strategy
    from backtester import Backtester

logger = logging.getLogger(__name__) # Logger für dieses Modul

class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        logger.info("FinanceApp.__init__: Initialisierung gestartet.")

        self.title("Finance Analysis Tool")
        self.geometry("1200x800")
        # Appearance Mode wird beim Start gesetzt, kein separates Logging nötig, außer es gibt Probleme
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.data_frame = None
        self.backtest_results_fig = None
        self.current_main_frame = None
        self._active_params_display_frame = None # Initialisiert für Klarheit
        self.current_strategy_param_vars = {} # Initialisiert für Klarheit

        # --- Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)
        logger.debug(f"FinanceApp.__init__: Sidebar erstellt (ID: {id(self.sidebar_frame)})")


        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="FinanceTool", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.data_button = ctk.CTkButton(self.sidebar_frame, text="Datenabruf", command=self.show_data_frame)
        self.data_button.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.backtest_button = ctk.CTkButton(self.sidebar_frame, text="Backtesting", command=self.show_backtesting_frame)
        self.backtest_button.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(0,20), sticky="ew")

        logger.info("FinanceApp.__init__: Initialisiere mit Datenabruf-Frame.")
        self.show_data_frame() # Initialansicht
        logger.info("FinanceApp.__init__: Initialisierung beendet.")


    def change_appearance_mode_event(self, new_appearance_mode: str):
        logger.info(f"change_appearance_mode_event: Modus geändert zu '{new_appearance_mode}'.")
        ctk.set_appearance_mode(new_appearance_mode)

    def clear_main_frame(self):
        logger.debug("clear_main_frame: Aufgerufen.")
        if self.current_main_frame and self.current_main_frame.winfo_exists():
            old_frame_id = id(self.current_main_frame)
            logger.debug(f"clear_main_frame: Zerstöre alten self.current_main_frame (ID: {old_frame_id}, Name: {str(self.current_main_frame)}).")
            try:
                # Zerstöre Kinder zuerst, um potenzielle Probleme zu minimieren
                for widget in self.current_main_frame.winfo_children():
                    logger.debug(f"clear_main_frame: Zerstöre Kind-Widget (ID: {id(widget)}, Name: {str(widget)}) von altem Mainframe.")
                    widget.destroy()
                self.current_main_frame.destroy()
                logger.debug(f"clear_main_frame: Alter self.current_main_frame (ID: {old_frame_id}) erfolgreich zerstört.")
            except Exception as e:
                logger.error(f"clear_main_frame: Fehler beim Zerstören des alten Mainframes (ID: {old_frame_id}): {e}", exc_info=True)
        elif self.current_main_frame:
             logger.warning(f"clear_main_frame: Alter self.current_main_frame (ID: {id(self.current_main_frame)}) existiert nicht mehr laut winfo_exists().")
        else:
            logger.debug("clear_main_frame: Kein self.current_main_frame zum Zerstören vorhanden.")

        self.current_main_frame = ctk.CTkFrame(self, corner_radius=5)
        self.current_main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.current_main_frame.grid_columnconfigure(0, weight=1)
        self.current_main_frame.grid_rowconfigure(1, weight=1)
        logger.debug(f"clear_main_frame: Neuer self.current_main_frame erstellt (ID: {id(self.current_main_frame)}, Name: {str(self.current_main_frame)}).")


    def show_data_frame(self):
        logger.info("show_data_frame: Aufgerufen.")
        self.clear_main_frame()

        logger.debug("show_data_frame: Erstelle UI-Elemente für Datenabruf.")
        input_controls_frame = ctk.CTkFrame(self.current_main_frame)
        input_controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(input_controls_frame, text="Ticker:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ticker_entry = ctk.CTkEntry(input_controls_frame, placeholder_text="z.B. AAPL, ^GDAXI")
        self.ticker_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.ticker_entry.insert(0, "AAPL")

        ctk.CTkLabel(input_controls_frame, text="Startdatum:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.start_date_entry = ctk.CTkEntry(input_controls_frame, placeholder_text="JJJJ-MM-TT")
        self.start_date_entry.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        self.start_date_entry.insert(0, (datetime.date.today() - datetime.timedelta(days=365)).strftime("%Y-%m-%d"))

        ctk.CTkLabel(input_controls_frame, text="Enddatum:").grid(row=0, column=4, padx=5, pady=5, sticky="w")
        self.end_date_entry = ctk.CTkEntry(input_controls_frame, placeholder_text="JJJJ-MM-TT")
        self.end_date_entry.grid(row=0, column=5, padx=5, pady=5, sticky="ew")
        self.end_date_entry.insert(0, datetime.date.today().strftime("%Y-%m-%d"))

        ctk.CTkLabel(input_controls_frame, text="Intervall:").grid(row=0, column=6, padx=5, pady=5, sticky="w")
        self.interval_options = ["1d", "1wk", "1mo", "1h", "30m", "5m"]
        self.interval_var = ctk.StringVar(value="1d")
        self.interval_menu = ctk.CTkOptionMenu(input_controls_frame, variable=self.interval_var, values=self.interval_options)
        self.interval_menu.grid(row=0, column=7, padx=5, pady=5, sticky="ew")

        self.fetch_button = ctk.CTkButton(input_controls_frame, text="Daten abrufen", command=self.fetch_data_and_display)
        self.fetch_button.grid(row=0, column=8, padx=10, pady=5)

        input_controls_frame.grid_columnconfigure(1, weight=1)
        input_controls_frame.grid_columnconfigure(3, weight=1)
        input_controls_frame.grid_columnconfigure(5, weight=1)

        self.data_display_frame = ctk.CTkFrame(self.current_main_frame)
        self.data_display_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.data_display_frame.grid_columnconfigure(0, weight=1)
        self.data_display_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.data_display_frame, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(self.data_display_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)
        hsb = ttk.Scrollbar(self.data_display_frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=hsb.set)

        style = ttk.Style()
        try:
            current_theme = style.theme_use()
            logger.debug(f"show_data_frame: Aktuelles ttk Theme: {current_theme}")
            # Versuche, ein Theme zu verwenden, das besser zu CTk passt, falls nicht schon optimal
            if 'clam' in style.theme_names():
                style.theme_use('clam')
            style.configure("Treeview", rowheight=25, font=('Arial', 10)) # Beispiel Font
            style.configure("Treeview.Heading", font=('Arial', 11, 'bold'))
        except Exception as e:
            logger.warning(f"show_data_frame: Fehler beim Konfigurieren des ttk Styles: {e}")

        logger.info("show_data_frame: Beendet.")


    def fetch_data_and_display(self):
        logger.info("fetch_data_and_display: Aufgerufen.")
        ticker = self.ticker_entry.get() if hasattr(self, 'ticker_entry') and self.ticker_entry.winfo_exists() else ""
        start_date = self.start_date_entry.get() if hasattr(self, 'start_date_entry') and self.start_date_entry.winfo_exists() else ""
        end_date = self.end_date_entry.get() if hasattr(self, 'end_date_entry') and self.end_date_entry.winfo_exists() else ""
        interval = self.interval_var.get() # StringVar ist immer sicher
        logger.debug(f"fetch_data_and_display: Parameter - Ticker: '{ticker}', Start: '{start_date}', Ende: '{end_date}', Intervall: '{interval}'")

        if not ticker or not start_date or not end_date:
            logger.warning("fetch_data_and_display: Eingabefelder unvollständig.")
            messagebox.showerror("Eingabefehler", "Bitte alle Felder ausfüllen.")
            return

        try:
            datetime.datetime.strptime(start_date, "%Y-%m-%d")
            datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            logger.warning(f"fetch_data_and_display: Ungültiges Datumsformat. Start: '{start_date}', Ende: '{end_date}'.")
            messagebox.showerror("Formatfehler", "Datumsformat muss JJJJ-MM-TT sein.")
            return

        logger.debug(f"fetch_data_and_display: Rufe fetch_data für Ticker '{ticker}'.")
        self.data_frame = fetch_data(ticker, start_date, end_date, interval)

        if not (hasattr(self, 'tree') and self.tree.winfo_exists()):
            logger.error("fetch_data_and_display: Treeview-Widget existiert nicht mehr. Breche Anzeige ab.")
            return

        for i in self.tree.get_children():
            self.tree.delete(i)
        self.tree["columns"] = []

        if self.data_frame is not None and not self.data_frame.empty:
            logger.info(f"fetch_data_and_display: Daten für '{ticker}' erfolgreich abgerufen ({len(self.data_frame)} Zeilen). Fülle Treeview.")
            cols = list(self.data_frame.columns)
            cols.insert(0, self.data_frame.index.name if self.data_frame.index.name else "Date")
            self.tree["columns"] = cols
            for col in cols:
                self.tree.heading(col, text=col)
                self.tree.column(col, width=100, anchor='center')
            for index, row in self.data_frame.iterrows():
                row_values = [index.strftime('%Y-%m-%d %H:%M:%S') if isinstance(index, pd.Timestamp) else str(index)]
                row_values.extend([f"{val:.2f}" if isinstance(val, float) else str(val) for val in row.values])
                self.tree.insert("", "end", values=row_values)

            stock_info = get_stock_info(ticker)
            if stock_info and 'longName' in stock_info and hasattr(self, 'logo_label') and self.logo_label.winfo_exists():
                 self.logo_label.configure(text=stock_info['longName'])
            elif hasattr(self, 'logo_label') and self.logo_label.winfo_exists():
                 self.logo_label.configure(text=ticker if ticker else "FinanceTool")

        elif self.data_frame is not None and self.data_frame.empty:
            logger.info(f"fetch_data_and_display: Keine Daten für '{ticker}' im Zeitraum gefunden.")
            messagebox.showinfo("Keine Daten", f"Keine Daten für {ticker} im angegebenen Zeitraum gefunden.")
            if hasattr(self, 'logo_label') and self.logo_label.winfo_exists():
                self.logo_label.configure(text=ticker if ticker else "FinanceTool")
        else:
            logger.error(f"fetch_data_and_display: Fehler beim Abrufen der Daten für '{ticker}'.")
            messagebox.showerror("Fehler", f"Fehler beim Abrufen der Daten für {ticker}.")
            if hasattr(self, 'logo_label') and self.logo_label.winfo_exists():
                self.logo_label.configure(text="FinanceTool")
        logger.info("fetch_data_and_display: Beendet.")


    def show_backtesting_frame(self):
        logger.info("show_backtesting_frame: Aufgerufen.")
        self.clear_main_frame()

        if self.data_frame is None or self.data_frame.empty:
            logger.warning("show_backtesting_frame: Keine Daten für Backtesting vorhanden. Zeige Info-Label.")
            ctk.CTkLabel(self.current_main_frame, text="Bitte zuerst Daten im 'Datenabruf'-Tab laden.",
                         font=ctk.CTkFont(size=16)).pack(pady=50, padx=20, fill="both", expand=True)
            return

        logger.debug("show_backtesting_frame: Erstelle UI-Elemente für Backtesting.")
        backtest_controls_frame = ctk.CTkFrame(self.current_main_frame)
        backtest_controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        logger.debug(f"show_backtesting_frame: backtest_controls_frame erstellt (ID: {id(backtest_controls_frame)})")


        ctk.CTkLabel(backtest_controls_frame, text="Strategie:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.strategy_options = ["MA_Crossover", "RSI"]
        current_strat_val = self.strategy_var.get() if hasattr(self, 'strategy_var') else "MA_Crossover"
        self.strategy_var = ctk.StringVar(value=current_strat_val) # Behalte ggf. alte Auswahl
        self.strategy_menu = ctk.CTkOptionMenu(backtest_controls_frame, variable=self.strategy_var, values=self.strategy_options, command=self.update_strategy_params_ui)
        self.strategy_menu.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        logger.debug(f"show_backtesting_frame: strategy_menu erstellt (ID: {id(self.strategy_menu)}) mit Strategie '{self.strategy_var.get()}'")

        self.strategy_params_container_frame = ctk.CTkFrame(backtest_controls_frame)
        self.strategy_params_container_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="ew")
        logger.debug(f"show_backtesting_frame: strategy_params_container_frame erstellt (ID: {id(self.strategy_params_container_frame)}, Exists: {self.strategy_params_container_frame.winfo_exists()})")

        # _active_params_display_frame wird in update_strategy_params_ui verwaltet und initial auf None gesetzt (in __init__)

        self.run_backtest_button = ctk.CTkButton(backtest_controls_frame, text="Backtest starten", command=self.run_backtest_and_display)
        self.run_backtest_button.grid(row=0, column=2, padx=10, pady=5)
        logger.debug(f"show_backtesting_frame: run_backtest_button erstellt (ID: {id(self.run_backtest_button)})")

        backtest_controls_frame.grid_columnconfigure(1, weight=1)

        if not hasattr(self, 'current_strategy_param_vars') or not self.current_strategy_param_vars: # Nur wenn leer oder nicht existent
            self.current_strategy_param_vars = {}

        logger.debug(f"show_backtesting_frame: Rufe update_strategy_params_ui mit Strategie '{self.strategy_var.get()}'.")
        self.update_strategy_params_ui(self.strategy_var.get())
        logger.debug("show_backtesting_frame: update_strategy_params_ui zurückgekehrt.")

        self.backtest_display_frame = ctk.CTkFrame(self.current_main_frame)
        self.backtest_display_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.backtest_display_frame.grid_columnconfigure(0, weight=1)
        self.backtest_display_frame.grid_rowconfigure(0, weight=3)
        self.backtest_display_frame.grid_rowconfigure(1, weight=1)
        logger.debug(f"show_backtesting_frame: backtest_display_frame erstellt (ID: {id(self.backtest_display_frame)})")


        self.chart_frame = ctk.CTkFrame(self.backtest_display_frame)
        self.chart_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        logger.debug(f"show_backtesting_frame: chart_frame erstellt (ID: {id(self.chart_frame)}, Exists: {self.chart_frame.winfo_exists()})")

        self.metrics_text = ctk.CTkTextbox(self.backtest_display_frame, height=150, wrap="word", font=("Arial", 12))
        self.metrics_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.metrics_text.insert("0.0", "Performance Metriken werden hier angezeigt...")
        self.metrics_text.configure(state="disabled")
        logger.debug(f"show_backtesting_frame: metrics_text erstellt (ID: {id(self.metrics_text)}, Exists: {self.metrics_text.winfo_exists()})")
        logger.info("show_backtesting_frame: Beendet.")


    def update_strategy_params_ui(self, strategy_name):
        logger.info(f"update_strategy_params_ui: Aufgerufen mit strategy_name='{strategy_name}'.")

        # Container muss existieren
        if not (hasattr(self, 'strategy_params_container_frame') and self.strategy_params_container_frame.winfo_exists()):
            logger.error("update_strategy_params_ui: strategy_params_container_frame existiert nicht! UI-Update abgebrochen.")
            return

        if self._active_params_display_frame is not None and self._active_params_display_frame.winfo_exists():
            old_active_frame_id = id(self._active_params_display_frame)
            logger.debug(f"update_strategy_params_ui: Zerstöre alten _active_params_display_frame (ID: {old_active_frame_id}, Name: {str(self._active_params_display_frame)}).")
            try:
                self._active_params_display_frame.destroy()
                logger.debug(f"update_strategy_params_ui: Alter _active_params_display_frame (ID: {old_active_frame_id}) erfolgreich zerstört.")
            except Exception as e:
                 logger.error(f"update_strategy_params_ui: Fehler beim Zerstören des alten _active_params_display_frame (ID: {old_active_frame_id}): {e}", exc_info=True)
        elif self._active_params_display_frame:
            logger.warning(f"update_strategy_params_ui: Alter _active_params_display_frame (ID: {id(self._active_params_display_frame)}) existiert nicht mehr laut winfo_exists().")

        self._active_params_display_frame = ctk.CTkFrame(self.strategy_params_container_frame)
        self._active_params_display_frame.pack(fill="x", expand=True, padx=0, pady=0)
        logger.debug(f"update_strategy_params_ui: Neuer _active_params_display_frame erstellt (ID: {id(self._active_params_display_frame)}, Name: {str(self._active_params_display_frame)}, Parent: {str(self.strategy_params_container_frame)}).")

        self.current_strategy_param_vars = {}
        logger.debug(f"update_strategy_params_ui: self.current_strategy_param_vars geleert.")

        param_configs = []
        if strategy_name == "MA_Crossover":
            param_configs = [
                ("Short Window:", "short_window", "20", 0, 0), ("Long Window:", "long_window", "50", 0, 2)
            ]
        elif strategy_name == "RSI":
            param_configs = [
                ("RSI Window:", "rsi_window", "14", 0, 0), ("Oversold:", "rsi_oversold", "30", 0, 2),
                ("Overbought:", "rsi_overbought", "70", 0, 4)
            ]

        for label_text, key, default_value, r, c_label in param_configs:
            ctk.CTkLabel(self._active_params_display_frame, text=label_text).grid(row=r, column=c_label, padx=5, pady=2, sticky="w")
            var = ctk.StringVar(value=default_value)
            entry = ctk.CTkEntry(self._active_params_display_frame, width=60, textvariable=var)
            entry.grid(row=r, column=c_label + 1, padx=5, pady=2)
            self.current_strategy_param_vars[key] = var
            logger.debug(f"update_strategy_params_ui: Parameter '{key}' erstellt (StringVar ID: {id(var)}, Entry ID: {id(entry)}).")

        # Allgemeine Parameter
        common_params_row = 1 # Nächste Zeile für allgemeine Parameter
        ctk.CTkLabel(self._active_params_display_frame, text="Shares/Trade:").grid(row=common_params_row, column=0, padx=5, pady=2, sticky="w")
        spt_var = ctk.StringVar(value="10")
        entry_spt = ctk.CTkEntry(self._active_params_display_frame, width=60, textvariable=spt_var)
        entry_spt.grid(row=common_params_row, column=1, padx=5, pady=2)
        self.current_strategy_param_vars['shares_per_trade'] = spt_var
        logger.debug(f"update_strategy_params_ui: Parameter 'shares_per_trade' erstellt (StringVar ID: {id(spt_var)}, Entry ID: {id(entry_spt)}).")

        ctk.CTkLabel(self._active_params_display_frame, text="Initial Capital:").grid(row=common_params_row, column=2, padx=5, pady=2, sticky="w")
        ic_var = ctk.StringVar(value="10000")
        entry_ic = ctk.CTkEntry(self._active_params_display_frame, width=80, textvariable=ic_var)
        entry_ic.grid(row=common_params_row, column=3, padx=5, pady=2)
        self.current_strategy_param_vars['initial_capital'] = ic_var
        logger.debug(f"update_strategy_params_ui: Parameter 'initial_capital' erstellt (StringVar ID: {id(ic_var)}, Entry ID: {id(entry_ic)}).")
        logger.info(f"update_strategy_params_ui: Beendet für strategy_name='{strategy_name}'.")


    def run_backtest_and_display(self):
        logger.info("run_backtest_and_display: Aufgerufen.")
        try:
            logger.debug("run_backtest_and_display: Versuche Fokus auf Hauptfenster zu setzen.")
            self.focus_set()
            logger.debug("run_backtest_and_display: Fokus auf Hauptfenster gesetzt.")
        except Exception as e:
            logger.warning(f"run_backtest_and_display: Fehler beim Setzen des Fokus: {e}", exc_info=True)

        if self.data_frame is None or self.data_frame.empty:
            logger.warning("run_backtest_and_display: data_frame ist leer oder None.")
            messagebox.showerror("Fehler", "Keine Daten für Backtesting vorhanden. Bitte zuerst Daten abrufen.")
            return

        strategy_name = self.strategy_var.get() # StringVar ist sicher
        logger.debug(f"run_backtest_and_display: Strategie: '{strategy_name}'. Parameter-Keys: {list(self.current_strategy_param_vars.keys())}")

        params = {}
        try:
            for key, str_var in self.current_strategy_param_vars.items():
                if not isinstance(str_var, ctk.StringVar): # Zusätzliche Sicherheitsprüfung
                    logger.error(f"run_backtest_and_display: Eintrag für '{key}' in current_strategy_param_vars ist keine StringVar, sondern {type(str_var)}.")
                    messagebox.showerror("Interner Fehler", f"Falscher Typ für Parameter '{key}'.")
                    return # Frühzeitiger Ausstieg

                logger.debug(f"run_backtest_and_display: Lese Parameter '{key}' (StringVar ID: {id(str_var)}).")
                value_str = str_var.get()
                logger.debug(f"run_backtest_and_display: Parameter '{key}' Rohwert von StringVar: '{value_str}'.")
                if key in ['short_window', 'long_window', 'rsi_window', 'rsi_oversold', 'rsi_overbought', 'shares_per_trade']:
                    params[key] = int(value_str)
                elif key == 'initial_capital':
                     params[key] = float(value_str)
                else:
                    params[key] = value_str
                logger.debug(f"run_backtest_and_display: Parameter '{key}' konvertierter Wert: {params[key]}.")
        except ValueError as e:
            logger.error(f"run_backtest_and_display: ValueError beim Konvertieren der Parameter: '{e}'. Key: '{key}', Wert: '{value_str}'.", exc_info=False)
            messagebox.showerror("Parameterfehler", f"Bitte gültige Zahlen für Strategieparameter eingeben (Fehler bei '{key}').")
            self.after(10, lambda: self._update_backtest_results_ui({"error": f"Ungültiger Parameter '{key}': {value_str}"}, None))
            return
        except Exception as e: # Fängt auch TclError ab, falls str_var.get() fehlschlägt
            logger.error(f"run_backtest_and_display: Unerwarteter Fehler beim Abrufen/Konvertieren von Parameter '{key}': {e}", exc_info=True)
            messagebox.showerror("Parameterfehler", f"Fehler beim Lesen des Parameters '{key}'.")
            self.after(10, lambda: self._update_backtest_results_ui({"error": f"Fehler bei Parameter '{key}': {e}"}, None))
            return

        logger.debug(f"run_backtest_and_display: Parameter für Strategie '{strategy_name}': {params}")

        # Extrahiere Backtester-spezifische Parameter
        initial_capital = params.pop('initial_capital', 10000.0)
        shares_per_trade_val = params.pop('shares_per_trade', None)

        # Temporär feste Werte für Kommission und Slippage
        commission = 0.0
        slippage = 0.0

        fig = None # Initialisiere fig für den Fehlerfall
        metrics = {"info": "Backtest gestartet..."} # Initiale Metriken

        try:
            logger.info(f"run_backtest_and_display: Setup Strategie '{strategy_name}'.")
            strategy_instance = setup_strategy(strategy_name, self.data_frame.copy(), params)
            if not strategy_instance:
                logger.error(f"run_backtest_and_display: Strategie '{strategy_name}' konnte nicht initialisiert werden.")
                messagebox.showerror("Strategiefehler", f"Strategie {strategy_name} konnte nicht initialisiert werden.")
                self.after(10, lambda: self._update_backtest_results_ui({"error": f"Strategie {strategy_name} nicht initialisiert"}, None))
                return

            logger.info(f"run_backtest_and_display: Initialisiere Backtester mit Kapital {initial_capital}.")
            backtester = Backtester(strategy_instance,
                                    initial_capital=initial_capital,
                                    commission_per_trade=commission,
                                    slippage_pct=slippage)

            logger.info(f"run_backtest_and_display: Starte Backtest-Lauf (Shares/Trade: {shares_per_trade_val}).")
            if shares_per_trade_val and shares_per_trade_val > 0 :
                 backtester.run_backtest(shares_per_trade=shares_per_trade_val)
            else:
                 logger.debug("run_backtest_and_display: Verwende capital_per_trade_pct=0.1 als Fallback.")
                 backtester.run_backtest(capital_per_trade_pct=0.1)
            logger.info("run_backtest_and_display: Backtest-Lauf beendet. Berechne Metriken.")

            metrics = backtester.calculate_performance_metrics()
            logger.info(f"run_backtest_and_display: Metriken berechnet: {metrics}")

            logger.debug("run_backtest_and_display: Erstelle Chart Figure.")
            fig = Figure(figsize=(8, 4), dpi=100)
            ax1 = fig.add_subplot(111)
            ax1.plot(backtester.portfolio_history.index, backtester.portfolio_history['total_value'], label='Portfolio Value', color='blue', lw=1.5)
            ax1.set_xlabel('Datum', fontsize=10)
            ax1.set_ylabel('Portfolio Wert (€)', color='blue', fontsize=10)
            ax1.tick_params(axis='y', labelcolor='blue', labelsize=8)
            ax1.tick_params(axis='x', labelsize=8, rotation=20)
            ax1.set_title(f'Portfolio Entwicklung ({strategy_name})', fontsize=12)
            ax1.grid(True, linestyle='--', alpha=0.6)

            ax2 = ax1.twinx()
            ax2.plot(backtester.data.index, backtester.data['Close'], label=f'{self.ticker_entry.get() if hasattr(self,"ticker_entry") and self.ticker_entry.winfo_exists() else "N/A"} Close', color='grey', alpha=0.5, lw=1)
            ax2.set_ylabel('Aktienkurs (€)', color='grey', fontsize=10)
            ax2.tick_params(axis='y', labelcolor='grey', labelsize=8)

            if backtester.results is not None and not backtester.results.empty:
                buys = backtester.results[backtester.results['type'] == 'Buy']
                sells = backtester.results[backtester.results['type'] == 'Sell']
                if not buys.empty:
                    ax2.plot(buys['timestamp'], buys['price'], '^', markersize=5, color='green', lw=0, label='Kauf')
                if not sells.empty:
                    ax2.plot(sells['timestamp'], sells['price'], 'v', markersize=5, color='red', lw=0, label='Verkauf')

            lines, labels = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines + lines2, labels + labels2, loc='upper left', fontsize=8)
            fig.tight_layout()
            logger.debug("run_backtest_and_display: Chart Figure erstellt.")

            logger.info("run_backtest_and_display: Plane verzögertes UI-Update für Ergebnisse.")
            self.after(10, lambda: self._update_backtest_results_ui(metrics, fig))

        except ValueError as e: # Dieser Block fängt spezifische ValueErrors aus dem Backtesting-Prozess
            logger.error(f"run_backtest_and_display: ValueError im Backtesting-Prozess: {e}", exc_info=True)
            messagebox.showerror("Parameterfehler", f"Fehler in den Parametern oder Daten: {e}")
            self.after(10, lambda: self._update_backtest_results_ui({"error": str(e)}, fig)) # fig könnte None sein
        except Exception as e: # Fängt alle anderen Fehler im Backtesting-Prozess, einschließlich potenzieller TclErrors
            logger.critical(f"run_backtest_and_display: Unerwarteter Fehler im Backtest-Prozess: {e}", exc_info=True)
            messagebox.showerror("Backtest Fehler", f"Ein unerwarteter Fehler ist aufgetreten: {e}")
            import traceback
            error_info = traceback.format_exc()
            self.after(10, lambda: self._update_backtest_results_ui({"error": str(e), "details": error_info.splitlines()[-1] if error_info else "N/A"}, fig)) # fig könnte None sein
        logger.info("run_backtest_and_display: Beendet.")


    def _update_backtest_results_ui(self, metrics, fig):
        logger.info("_update_backtest_results_ui: Aufgerufen.")
        logger.debug(f"_update_backtest_results_ui: Übergebene Metriken: {metrics}, Figure vorhanden: {fig is not None}")

        # Sicherstellen, dass die UI-Elemente existieren, bevor darauf zugegriffen wird
        if not (hasattr(self, 'metrics_text') and self.metrics_text and self.metrics_text.winfo_exists()):
            logger.error("_update_backtest_results_ui: metrics_text Widget existiert nicht oder wurde zerstört.")
            return

        self.metrics_text.configure(state="normal")
        self.metrics_text.delete("0.0", "end")

        try:
            ticker_display_name = self.ticker_entry.get() if hasattr(self,"ticker_entry") and self.ticker_entry and self.ticker_entry.winfo_exists() else "N/A"
        except Exception as e:
            logger.warning(f"_update_backtest_results_ui: Fehler beim Abrufen von ticker_entry: {e}")
            ticker_display_name = "N/A"

        try:
            strategy_display_name = self.strategy_var.get() if hasattr(self,"strategy_var") else "N/A"
        except Exception as e:
            logger.warning(f"_update_backtest_results_ui: Fehler beim Abrufen von strategy_var: {e}")
            strategy_display_name = "N/A"


        metrics_str = f"Backtest für {strategy_display_name} auf {ticker_display_name}:\n"
        if "error" in metrics:
            metrics_str += f"  Fehler: {metrics['error']}\n"
            if "details" in metrics:
                 metrics_str += f"  Details: {metrics['details']}\n"
        else:
            for key, value in metrics.items():
                metrics_str += f"  {key.replace('_', ' ').capitalize()}: {value}\n"
        self.metrics_text.insert("0.0", metrics_str)
        self.metrics_text.configure(state="disabled")
        logger.debug(f"_update_backtest_results_ui: metrics_text aktualisiert.")


        if not (hasattr(self, 'chart_frame') and self.chart_frame and self.chart_frame.winfo_exists()):
            logger.error("_update_backtest_results_ui: chart_frame Widget existiert nicht oder wurde zerstört.")
            return

        for widget in self.chart_frame.winfo_children():
            logger.debug(f"_update_backtest_results_ui: Zerstöre altes Kind-Widget im chart_frame (ID: {id(widget)}, Name: {str(widget)})")
            widget.destroy()

        if fig:
            logger.debug(f"_update_backtest_results_ui: Zeichne neuen Chart (Figure ID: {id(fig)}) im chart_frame (ID: {id(self.chart_frame)}).")
            try:
                canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
                canvas_widget = canvas.get_tk_widget()
                canvas_widget.pack(side=ctk.TOP, fill=ctk.BOTH, expand=True)
                canvas.draw()
                logger.debug(f"_update_backtest_results_ui: Chart erfolgreich gezeichnet und gepackt.")
            except Exception as e:
                logger.error(f"_update_backtest_results_ui: Fehler beim Erstellen/Zeichnen des Canvas: {e}", exc_info=True)
                ctk.CTkLabel(self.chart_frame, text="Fehler beim Anzeigen des Charts.").pack(padx=10, pady=10)
        else:
            logger.info("_update_backtest_results_ui: Keine Figure zum Zeichnen vorhanden (z.B. Fehlerfall). Zeige Info-Label.")
            ctk.CTkLabel(self.chart_frame, text="Chart konnte nicht geladen werden oder Fehler beim Backtest.").pack(padx=10, pady=10)
        logger.info("_update_backtest_results_ui: Beendet.")


if __name__ == '__main__':
    # Wichtiger Hinweis: Damit die relativen Importe funktionieren, wenn gui.py direkt ausgeführt wird,
    # muss das Hauptverzeichnis (finance_analysis_tool) im PYTHONPATH sein oder
    # man startet es als Modul vom Hauptverzeichnis: python -m finance_tool.gui

    # Für Testzwecke kann man sys.path anpassen, aber das ist kein guter Stil für die Distribution:
    # import sys
    # import os
    # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Minimal logging setup for direct run of gui.py for testing
    if not logging.getLogger().hasHandlers(): # Configure only if not already configured by main.py
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    app = FinanceApp()
    app.mainloop()
