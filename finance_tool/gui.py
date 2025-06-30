# finance_tool/gui.py

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import datetime

# Importiere Module aus dem Paket finance_tool
# (Annahme: GUI wird aus dem Hauptverzeichnis des Projekts gestartet,
# oder finance_tool ist im PYTHONPATH)
try:
    from .data_fetcher import fetch_data, get_stock_info
    from .strategies import setup_strategy
    from .backtester import Backtester
except ImportError:
    # Fallback für direkten Testlauf von gui.py (nicht ideal für Produktion)
    print("Versuche Fallback-Importe für GUI...")
    from data_fetcher import fetch_data, get_stock_info
    from strategies import setup_strategy
    from backtester import Backtester


class FinanceApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Finance Analysis Tool")
        self.geometry("1200x800")
        ctk.set_appearance_mode("System")  # System, Dark, Light
        ctk.set_default_color_theme("blue") # "blue", "green", "dark-blue"

        self.data_frame = None # Für abgerufene Finanzdaten
        self.backtest_results_fig = None # Für Backtesting-Chart

        # --- Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        self.logo_label = ctk.CTkLabel(self.sidebar_frame, text="FinanceTool", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self.data_button = ctk.CTkButton(self.sidebar_frame, text="Datenabruf", command=self.show_data_frame)
        self.data_button.grid(row=1, column=0, padx=20, pady=10, sticky="ew")

        self.backtest_button = ctk.CTkButton(self.sidebar_frame, text="Backtesting", command=self.show_backtesting_frame)
        self.backtest_button.grid(row=2, column=0, padx=20, pady=10, sticky="ew")

        # Appearance Mode OptionMenu
        self.appearance_mode_label = ctk.CTkLabel(self.sidebar_frame, text="Appearance Mode:", anchor="w")
        self.appearance_mode_label.grid(row=5, column=0, padx=20, pady=(10, 0))
        self.appearance_mode_optionemenu = ctk.CTkOptionMenu(self.sidebar_frame, values=["Light", "Dark", "System"],
                                                                       command=self.change_appearance_mode_event)
        self.appearance_mode_optionemenu.grid(row=6, column=0, padx=20, pady=(0,20), sticky="ew")


        # --- Hauptfenster-Frames (werden bei Bedarf angezeigt) ---
        self.current_main_frame = None

        # Initialansicht
        self.show_data_frame()


    def change_appearance_mode_event(self, new_appearance_mode: str):
        ctk.set_appearance_mode(new_appearance_mode)

    def clear_main_frame(self):
        if self.current_main_frame:
            for widget in self.current_main_frame.winfo_children():
                widget.destroy()
            self.current_main_frame.destroy()
        self.current_main_frame = ctk.CTkFrame(self, corner_radius=5)
        self.current_main_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        self.current_main_frame.grid_columnconfigure(0, weight=1) # Für zentrierte Inhalte
        self.current_main_frame.grid_rowconfigure(1, weight=1)    # Damit Treeview/Chart wachsen kann


    def show_data_frame(self):
        self.clear_main_frame()

        # --- Eingabebereich für Datenabruf ---
        input_controls_frame = ctk.CTkFrame(self.current_main_frame)
        input_controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(input_controls_frame, text="Ticker:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.ticker_entry = ctk.CTkEntry(input_controls_frame, placeholder_text="z.B. AAPL, ^GDAXI")
        self.ticker_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.ticker_entry.insert(0, "AAPL") # Default

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

        input_controls_frame.grid_columnconfigure(1, weight=1) # Ticker-Eingabe soll wachsen
        input_controls_frame.grid_columnconfigure(3, weight=1) # Startdatum-Eingabe soll wachsen
        input_controls_frame.grid_columnconfigure(5, weight=1) # Enddatum-Eingabe soll wachsen

        # --- Bereich für Datenanzeige (Treeview) ---
        self.data_display_frame = ctk.CTkFrame(self.current_main_frame)
        self.data_display_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.data_display_frame.grid_columnconfigure(0, weight=1)
        self.data_display_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(self.data_display_frame, show="headings")
        self.tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbars für Treeview
        vsb = ttk.Scrollbar(self.data_display_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        hsb = ttk.Scrollbar(self.data_display_frame, orient="horizontal", command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky="ew")
        self.tree.configure(xscrollcommand=hsb.set)

        # Style für Treeview (damit es besser zum CTk-Theme passt)
        style = ttk.Style()
        # print(style.theme_names()) # Zeigt verfügbare Themes
        # style.theme_use("clam") # Oder "default", "alt", "classic"
        style.configure("Treeview", rowheight=25, font=('Arial', 10))
        style.configure("Treeview.Heading", font=('Arial', 11, 'bold'))
        # Weitere Anpassungen sind möglich, aber komplexer, um CTk perfekt zu matchen


    def fetch_data_and_display(self):
        ticker = self.ticker_entry.get()
        start_date = self.start_date_entry.get()
        end_date = self.end_date_entry.get()
        interval = self.interval_var.get()

        if not ticker or not start_date or not end_date:
            messagebox.showerror("Eingabefehler", "Bitte alle Felder ausfüllen.")
            return

        try:
            # Validierung der Datumsformate (einfach)
            datetime.datetime.strptime(start_date, "%Y-%m-%d")
            datetime.datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Formatfehler", "Datumsformat muss JJJJ-MM-TT sein.")
            return

        self.data_frame = fetch_data(ticker, start_date, end_date, interval)

        # Treeview leeren
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.tree["columns"] = []

        if self.data_frame is not None and not self.data_frame.empty:
            # Spalten für Treeview setzen (Index als erste Spalte)
            cols = list(self.data_frame.columns)
            if self.data_frame.index.name:
                 cols.insert(0, self.data_frame.index.name)
            else:
                 cols.insert(0, "Date") # Fallback Name

            self.tree["columns"] = cols
            for col in cols:
                self.tree.heading(col, text=col)
                self.tree.column(col, width=100, anchor='center') # Breite anpassen

            # Daten einfügen
            for index, row in self.data_frame.iterrows():
                row_values = [index.strftime('%Y-%m-%d %H:%M:%S') if isinstance(index, pd.Timestamp) else str(index)]
                row_values.extend([f"{val:.2f}" if isinstance(val, float) else str(val) for val in row.values])
                self.tree.insert("", "end", values=row_values)

            # Info anzeigen
            stock_info = get_stock_info(ticker)
            if stock_info and 'longName' in stock_info:
                 self.logo_label.configure(text=stock_info['longName']) # Aktualisiere Label mit Firmenname
            else:
                 self.logo_label.configure(text=ticker if ticker else "FinanceTool")


        elif self.data_frame is not None and self.data_frame.empty:
            messagebox.showinfo("Keine Daten", f"Keine Daten für {ticker} im angegebenen Zeitraum gefunden.")
            self.logo_label.configure(text=ticker if ticker else "FinanceTool")
        else:
            messagebox.showerror("Fehler", f"Fehler beim Abrufen der Daten für {ticker}.")
            self.logo_label.configure(text="FinanceTool")


    def show_backtesting_frame(self):
        self.clear_main_frame()

        if self.data_frame is None or self.data_frame.empty:
            ctk.CTkLabel(self.current_main_frame, text="Bitte zuerst Daten im 'Datenabruf'-Tab laden.",
                         font=ctk.CTkFont(size=16)).pack(pady=50)
            return

        # --- Eingabebereich für Backtesting ---
        backtest_controls_frame = ctk.CTkFrame(self.current_main_frame)
        backtest_controls_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        ctk.CTkLabel(backtest_controls_frame, text="Strategie:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.strategy_options = ["MA_Crossover", "RSI"] # Später erweiterbar
        self.strategy_var = ctk.StringVar(value="MA_Crossover")
        self.strategy_menu = ctk.CTkOptionMenu(backtest_controls_frame, variable=self.strategy_var, values=self.strategy_options, command=self.update_strategy_params_ui)
        self.strategy_menu.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Frame für Strategieparameter
        self.strategy_params_frame = ctk.CTkFrame(backtest_controls_frame)
        self.strategy_params_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        self.run_backtest_button = ctk.CTkButton(backtest_controls_frame, text="Backtest starten", command=self.run_backtest_and_display)
        self.run_backtest_button.grid(row=0, column=2, padx=10, pady=5)

        backtest_controls_frame.grid_columnconfigure(1, weight=1)
        self.update_strategy_params_ui("MA_Crossover") # Initiale Parameter anzeigen

        # Initialisiere das Dictionary für Strategieparameter-Variablen
        self.current_strategy_param_vars = {}


        # --- Bereich für Backtesting-Chart und Metriken ---
        self.backtest_display_frame = ctk.CTkFrame(self.current_main_frame)
        self.backtest_display_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.backtest_display_frame.grid_columnconfigure(0, weight=1)
        self.backtest_display_frame.grid_rowconfigure(0, weight=3) # Chart bekommt mehr Platz
        self.backtest_display_frame.grid_rowconfigure(1, weight=1) # Metriken

        self.chart_frame = ctk.CTkFrame(self.backtest_display_frame) # Für den Matplotlib Canvas
        self.chart_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.metrics_text = ctk.CTkTextbox(self.backtest_display_frame, height=150, wrap="word", font=("Arial", 12))
        self.metrics_text.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        self.metrics_text.insert("0.0", "Performance Metriken werden hier angezeigt...")
        self.metrics_text.configure(state="disabled")


    def update_strategy_params_ui(self, strategy_name):
        # Alte Parameter-Widgets entfernen
        for widget in self.strategy_params_frame.winfo_children():
            widget.destroy()

        self.current_strategy_param_vars = {} # Wird jetzt verwendet, um StringVars zu speichern

        if strategy_name == "MA_Crossover":
            ctk.CTkLabel(self.strategy_params_frame, text="Short Window:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
            sw_var = ctk.StringVar(value="20")
            entry_sw = ctk.CTkEntry(self.strategy_params_frame, width=60, textvariable=sw_var)
            entry_sw.grid(row=0, column=1, padx=5, pady=2)
            self.current_strategy_param_vars['short_window'] = sw_var

            ctk.CTkLabel(self.strategy_params_frame, text="Long Window:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
            lw_var = ctk.StringVar(value="50")
            entry_lw = ctk.CTkEntry(self.strategy_params_frame, width=60, textvariable=lw_var)
            entry_lw.grid(row=0, column=3, padx=5, pady=2)
            self.current_strategy_param_vars['long_window'] = lw_var

        elif strategy_name == "RSI":
            ctk.CTkLabel(self.strategy_params_frame, text="RSI Window:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
            rw_var = ctk.StringVar(value="14")
            entry_rw = ctk.CTkEntry(self.strategy_params_frame, width=60, textvariable=rw_var)
            entry_rw.grid(row=0, column=1, padx=5, pady=2)
            self.current_strategy_param_vars['rsi_window'] = rw_var

            ctk.CTkLabel(self.strategy_params_frame, text="Oversold:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
            os_var = ctk.StringVar(value="30")
            entry_os = ctk.CTkEntry(self.strategy_params_frame, width=60, textvariable=os_var)
            entry_os.grid(row=0, column=3, padx=5, pady=2)
            self.current_strategy_param_vars['rsi_oversold'] = os_var

            ctk.CTkLabel(self.strategy_params_frame, text="Overbought:").grid(row=0, column=4, padx=5, pady=2, sticky="w")
            ob_var = ctk.StringVar(value="70")
            entry_ob = ctk.CTkEntry(self.strategy_params_frame, width=60, textvariable=ob_var)
            entry_ob.grid(row=0, column=5, padx=5, pady=2)
            self.current_strategy_param_vars['rsi_overbought'] = ob_var

        # Allgemeine Parameter (Shares/Trade, Initial Capital)
        ctk.CTkLabel(self.strategy_params_frame, text="Shares/Trade:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        spt_var = ctk.StringVar(value="10")
        entry_spt = ctk.CTkEntry(self.strategy_params_frame, width=60, textvariable=spt_var)
        entry_spt.grid(row=1, column=1, padx=5, pady=2)
        self.current_strategy_param_vars['shares_per_trade'] = spt_var

        ctk.CTkLabel(self.strategy_params_frame, text="Initial Capital:").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        ic_var = ctk.StringVar(value="10000")
        entry_ic = ctk.CTkEntry(self.strategy_params_frame, width=80, textvariable=ic_var)
        entry_ic.grid(row=1, column=3, padx=5, pady=2)
        self.current_strategy_param_vars['initial_capital'] = ic_var


    def run_backtest_and_display(self):
        if self.data_frame is None or self.data_frame.empty:
            messagebox.showerror("Fehler", "Keine Daten für Backtesting vorhanden. Bitte zuerst Daten abrufen.")
            return

        strategy_name = self.strategy_var.get()
        params = {}
        try:
            for key, str_var in self.current_strategy_param_vars.items():
                value_str = str_var.get()
                if key in ['short_window', 'long_window', 'rsi_window', 'rsi_oversold', 'rsi_overbought', 'shares_per_trade']:
                    params[key] = int(value_str)
                elif key == 'initial_capital':
                     params[key] = float(value_str)
                else:
                    params[key] = value_str
        except ValueError:
            messagebox.showerror("Parameterfehler", "Bitte gültige Zahlen für Strategieparameter eingeben.")
            return

        # Extrahiere Backtester-spezifische Parameter
        initial_capital = params.pop('initial_capital', 10000.0)
        shares_per_trade = params.pop('shares_per_trade', None) # None, wenn nicht gesetzt oder ungültig
        # TODO: capital_per_trade_pct als Option hinzufügen

        # Temporär feste Werte für Kommission und Slippage
        commission = 0.0 # params.pop('commission', 0.0)
        slippage = 0.0 # params.pop('slippage', 0.0)

        try:
            strategy_instance = setup_strategy(strategy_name, self.data_frame.copy(), params)
            if not strategy_instance:
                messagebox.showerror("Strategiefehler", f"Strategie {strategy_name} konnte nicht initialisiert werden.")
                return

            backtester = Backtester(strategy_instance,
                                    initial_capital=initial_capital,
                                    commission_per_trade=commission,
                                    slippage_pct=slippage)

            if shares_per_trade and shares_per_trade > 0 :
                 backtester.run_backtest(shares_per_trade=shares_per_trade)
            else: # Fallback oder explizite Wahl für capital_per_trade_pct (hier nicht implementiert)
                 backtester.run_backtest(capital_per_trade_pct=0.1) # Default 10% Kapital


            # Ergebnisse anzeigen
            metrics = backtester.calculate_performance_metrics()
            self.metrics_text.configure(state="normal")
            self.metrics_text.delete("0.0", "end")
            metrics_str = f"Backtest für {strategy_name} auf {self.ticker_entry.get()}:\n"
            for key, value in metrics.items():
                metrics_str += f"  {key.replace('_', ' ').capitalize()}: {value}\n"
            self.metrics_text.insert("0.0", metrics_str)
            self.metrics_text.configure(state="disabled")

            # Chart anzeigen
            # Alten Chart entfernen, falls vorhanden
            for widget in self.chart_frame.winfo_children():
                widget.destroy()

            fig = Figure(figsize=(8, 4), dpi=100) # Angepasste Größe
            # Die plot_results Methode des Backtesters benötigt plt.show(), was hier nicht ideal ist.
            # Wir müssen die Plot-Logik anpassen oder hier neu implementieren.
            # Fürs Erste: Direkte Plot-Logik hier (vereinfacht)

            ax1 = fig.add_subplot(111)
            ax1.plot(backtester.portfolio_history.index, backtester.portfolio_history['total_value'], label='Portfolio Value', color='blue', lw=1.5)
            ax1.set_xlabel('Datum', fontsize=10)
            ax1.set_ylabel('Portfolio Wert (€)', color='blue', fontsize=10)
            ax1.tick_params(axis='y', labelcolor='blue', labelsize=8)
            ax1.tick_params(axis='x', labelsize=8, rotation=20)
            ax1.set_title(f'Portfolio Entwicklung ({strategy_name})', fontsize=12)
            ax1.grid(True, linestyle='--', alpha=0.6)

            ax2 = ax1.twinx()
            ax2.plot(backtester.data.index, backtester.data['Close'], label=f'{self.ticker_entry.get()} Close', color='grey', alpha=0.5, lw=1)
            ax2.set_ylabel('Aktienkurs (€)', color='grey', fontsize=10)
            ax2.tick_params(axis='y', labelcolor='grey', labelsize=8)

            # Handelssignale plotten
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

            canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
            canvas_widget = canvas.get_tk_widget()
            canvas_widget.pack(side=ctk.TOP, fill=ctk.BOTH, expand=True)
            canvas.draw()

        except ValueError as e:
            messagebox.showerror("Parameterfehler", f"Fehler in den Parametern oder Daten: {e}")
        except Exception as e:
            messagebox.showerror("Backtest Fehler", f"Ein unerwarteter Fehler ist aufgetreten: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    # Wichtiger Hinweis: Damit die relativen Importe funktionieren, wenn gui.py direkt ausgeführt wird,
    # muss das Hauptverzeichnis (finance_analysis_tool) im PYTHONPATH sein oder
    # man startet es als Modul vom Hauptverzeichnis: python -m finance_tool.gui

    # Für Testzwecke kann man sys.path anpassen, aber das ist kein guter Stil für die Distribution:
    # import sys
    # import os
    # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    app = FinanceApp()
    app.mainloop()
