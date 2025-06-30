# finance_tool/gui.py
import sys
import logging
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTabWidget, QMenuBar, QStatusBar, QSpacerItem, QSizePolicy,
    QTableView, QLineEdit, QDateEdit, QComboBox, QFileDialog, QTextEdit,
    QMessageBox, QGroupBox, QFormLayout, QDialog
)
from PyQt6.QtGui import QAction, QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, QDate
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg # Nutze Qt5Agg, da oft kompatibler, oder QtAgg wenn verfügbar
import pandas as pd
import numpy as np # Hinzugefügt für np.floating
from typing import Optional, List, Dict, Any


# Backend-Importe (angenommen, sie sind im PYTHONPATH oder relativ erreichbar)
try:
    from .data_fetcher import fetch_data, get_stock_info
    from .indicators import get_available_indicators # Funktion zum Abrufen von Indikator-Infos
    from .strategy_definition import StrategyDefinition, load_strategy_from_json
    from .data_pipeline import prepare_data_for_strategy
    from .strategy_engine import StrategyEvaluator
    from .backtester import Backtester
except ImportError as e:
    # Fallback für den Fall, dass die GUI direkt ausgeführt wird und das Paket nicht richtig erkannt wird
    logger.error(f"Standard-Importe fehlgeschlagen: {e}. Versuche alternative Importe für standalone Ausführung.")
    from data_fetcher import fetch_data, get_stock_info
    from indicators import get_available_indicators
    from strategy_definition import StrategyDefinition, load_strategy_from_json
    from data_pipeline import prepare_data_for_strategy
    from strategy_engine import StrategyEvaluator
    from backtester import Backtester


logger = logging.getLogger(__name__)

class DataFrameModel(QStandardItemModel):
    """Ein einfaches Modell, um einen Pandas DataFrame in einer QTableView anzuzeigen."""
    def __init__(self, data: pd.DataFrame, parent=None):
        super().__init__(parent)
        if data is None:
            return

        self.setHorizontalHeaderLabels(data.columns.tolist())

        for row_idx, row_data in data.iterrows():
            items = []
            # Index als erste Spalte hinzufügen, falls er benannt ist oder ein DatetimeIndex
            if data.index.name:
                items.append(QStandardItem(str(data.index.name))) # Header für Index
            elif isinstance(data.index, pd.DatetimeIndex):
                 items.append(QStandardItem(str(row_idx.strftime('%Y-%m-%d %H:%M:%S')) if isinstance(row_idx, pd.Timestamp) else str(row_idx)))
            else:
                items.append(QStandardItem(str(row_idx)))

            for val in row_data:
                items.append(QStandardItem(f"{val:.4f}" if isinstance(val, (float, np.floating)) else str(val)))
            self.appendRow(items)

    def setHorizontalHeaderLabels(self, labels: List[str]):
        # Wenn der Index als erste Spalte angezeigt wird, muss der Header angepasst werden
        if self.rowCount() > 0 and self.columnCount() == len(labels) + 1: # Index + Spalten
            if isinstance(self.parent().current_data_df.index, pd.DatetimeIndex): # Annahme: parent ist MainWindow
                 actual_header_labels = [self.parent().current_data_df.index.name or "Date"] + labels
            else:
                 actual_header_labels = [self.parent().current_data_df.index.name or "Index"] + labels
            super().setHorizontalHeaderLabels(actual_header_labels)
        else:
            super().setHorizontalHeaderLabels(labels)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        logger.info("MainWindow.__init__: Initialisierung gestartet.")

        self.setWindowTitle("Finance Analysis Tool (PyQt6)")
        self.setGeometry(100, 100, 1200, 800) # x, y, width, height

        # Zentrale Widget und Layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout(self.central_widget) # Hauptlayout für Sidebar und Tabs

        # Datenmodelle und Referenzen
        self.current_data_df: Optional[pd.DataFrame] = None
        self.current_strategy_def: Optional[StrategyDefinition] = None
        self.available_indicators_info: List[Dict[str, Any]] = []
        self.backtester_instance = Backtester() # Eine Instanz für die App

        # Matplotlib Canvas für Charts
        self.mpl_figure: Optional[Figure] = None
        self.mpl_canvas: Optional[FigureCanvasQTAgg] = None


        # Sidebar (links)
        self.sidebar_widget = QWidget()
        self.sidebar_layout = QVBoxLayout(self.sidebar_widget)
        self.sidebar_widget.setFixedWidth(200)
        # self.sidebar_widget.setStyleSheet("background-color: #f0f0f0;")

        self.app_title_label = QLabel("FinanceTool")
        font = self.app_title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self.app_title_label.setFont(font)
        self.app_title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sidebar_layout.addWidget(self.app_title_label)

        # Buttons für Sidebar
        self.btn_data_fetch = QPushButton("Datenabruf")
        self.btn_data_fetch.clicked.connect(self.show_data_fetch_tab)
        self.sidebar_layout.addWidget(self.btn_data_fetch)

        self.btn_indicators = QPushButton("Indikatoren")
        self.btn_indicators.clicked.connect(self.show_indicators_tab)
        self.sidebar_layout.addWidget(self.btn_indicators)

        self.btn_strategy_mgmt = QPushButton("Strategie Mgmt.")
        self.btn_strategy_mgmt.clicked.connect(self.show_strategy_mgmt_tab)
        self.sidebar_layout.addWidget(self.btn_strategy_mgmt)

        self.btn_backtesting = QPushButton("Backtesting")
        self.btn_backtesting.clicked.connect(self.show_backtesting_tab)
        self.sidebar_layout.addWidget(self.btn_backtesting)

        self.sidebar_layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        self.main_layout.addWidget(self.sidebar_widget)

        # Tab-Widget für Hauptinhalt (rechts)
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True) # Erlaubt das Schließen von Tabs
        self.tab_widget.tabCloseRequested.connect(self.close_tab)
        self.main_layout.addWidget(self.tab_widget)

        self._create_menu_bar()
        self._create_status_bar()

        # Lade verfügbare Indikatoren beim Start
        self._load_available_indicators()

        logger.info("MainWindow.__init__: Initialisierung beendet.")
        self.show_data_fetch_tab() # Start-Tab


    def _load_available_indicators(self):
        logger.debug("MainWindow._load_available_indicators: Lade verfügbare Indikatoren.")
        try:
            self.available_indicators_info = get_available_indicators()
            logger.info(f"{len(self.available_indicators_info)} Indikatoren geladen.")
        except Exception as e:
            logger.error(f"Fehler beim Laden der verfügbaren Indikatoren: {e}", exc_info=True)
            QMessageBox.warning(self, "Fehler", f"Konnte Indikatoren nicht laden: {e}")


    def _create_menu_bar(self):
        logger.debug("MainWindow._create_menu_bar: Erstelle Menüleiste.")
        self.menu_bar = self.menuBar() # QMenuBar Instanz von QMainWindow holen

        # Datei-Menü
        file_menu = self.menu_bar.addMenu("&Datei")
        exit_action = QAction("&Beenden", self)
        exit_action.triggered.connect(self.close) # Schließt die Anwendung
        file_menu.addAction(exit_action)

        # Ansicht-Menü (Beispiel)
        view_menu = self.menu_bar.addMenu("&Ansicht")
        # Hier könnten Aktionen zum Ein-/Ausblenden von Docks/Toolbars etc. hinzukommen

    def _create_status_bar(self):
        logger.debug("MainWindow._create_status_bar: Erstelle Statusleiste.")
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Bereit.", 3000) # Nachricht für 3 Sekunden


    def _add_tab(self, widget: QWidget, title: str, switch_to_tab: bool = True) -> int:
        """
        Fügt einen neuen Tab hinzu. Wenn ein Tab mit demselben Titel bereits existiert,
        wird dieser aktualisiert (Widget ausgetauscht) oder einfach zu ihm gewechselt.
        Gibt den Index des Tabs zurück.
        """
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == title:
                logger.debug(f"MainWindow._add_tab: Tab '{title}' existiert bereits. Aktualisiere Inhalt oder wechsle.")
                old_widget = self.tab_widget.widget(i)
                if old_widget is not widget: # Nur austauschen, wenn es ein neues Widget ist
                    self.tab_widget.removeTab(i)
                    # old_widget.deleteLater() # Sicherstellen, dass altes Widget gelöscht wird
                    index = self.tab_widget.insertTab(i, widget, title)
                else:
                    index = i

                if switch_to_tab:
                    self.tab_widget.setCurrentIndex(index)
                return index

        index = self.tab_widget.addTab(widget, title)
        if switch_to_tab:
            self.tab_widget.setCurrentIndex(index)
        logger.info(f"MainWindow._add_tab: Neuer Tab '{title}' an Index {index} hinzugefügt und ausgewählt.")
        return index

    def close_tab(self, index: int):
        tab_text = self.tab_widget.tabText(index)
        logger.info(f"MainWindow.close_tab: Schließe Tab mit Index {index} ('{tab_text}').")

        # Spezifische Aufräumarbeiten, falls nötig (z.B. Matplotlib Canvas)
        if tab_text == "Backtest Ergebnisse":
            if self.mpl_canvas and self.mpl_canvas.parent() is not None:
                logger.debug("MainWindow.close_tab: Entferne Matplotlib Canvas aus Backtest-Ergebnis-Tab.")
                self.mpl_canvas.setParent(None)
                self.mpl_canvas.deleteLater()
                self.mpl_canvas = None
                self.mpl_figure = None # Auch Figur freigeben

        widget_to_close = self.tab_widget.widget(index)
        self.tab_widget.removeTab(index)
        if widget_to_close:
            widget_to_close.deleteLater()


    def show_data_fetch_tab(self):
        logger.info("MainWindow.show_data_fetch_tab: Erstelle/zeige Datenabruf-Tab.")

        # Prüfe, ob Tab schon existiert
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Datenabruf":
                self.tab_widget.setCurrentIndex(i)
                logger.debug("MainWindow.show_data_fetch_tab: Wechsle zu existierendem Tab 'Datenabruf'.")
                return

        data_fetch_widget = QWidget()
        main_v_layout = QVBoxLayout(data_fetch_widget)

        # Eingabebereich
        input_groupbox = QGroupBox("Dateneingabe")
        form_layout = QFormLayout()

        self.df_ticker_edit = QLineEdit("AAPL")
        self.df_start_date_edit = QDateEdit(QDate.currentDate().addYears(-1))
        self.df_start_date_edit.setCalendarPopup(True)
        self.df_start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.df_end_date_edit = QDateEdit(QDate.currentDate())
        self.df_end_date_edit.setCalendarPopup(True)
        self.df_end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.df_interval_combo = QComboBox()
        self.df_interval_combo.addItems(["1d", "1wk", "1mo", "1h", "30m", "5m"])

        form_layout.addRow("Ticker:", self.df_ticker_edit)
        form_layout.addRow("Startdatum:", self.df_start_date_edit)
        form_layout.addRow("Enddatum:", self.df_end_date_edit)
        form_layout.addRow("Intervall:", self.df_interval_combo)

        fetch_button = QPushButton("Daten abrufen")
        fetch_button.clicked.connect(self._fetch_data_action)
        form_layout.addRow(fetch_button)
        input_groupbox.setLayout(form_layout)
        main_v_layout.addWidget(input_groupbox)

        # Anzeigebereich (QTableView)
        self.data_table_view = QTableView()
        self.data_table_view.setSortingEnabled(True)
        self.data_table_view.setAlternatingRowColors(True)
        self.data_table_view.horizontalHeader().setStretchLastSection(True)
        main_v_layout.addWidget(self.data_table_view)

        self._add_tab(data_fetch_widget, "Datenabruf")

    def _fetch_data_action(self):
        ticker = self.df_ticker_edit.text()
        start_date = self.df_start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.df_end_date_edit.date().toString("yyyy-MM-dd")
        interval = self.df_interval_combo.currentText()
        logger.info(f"Datenabruf gestartet für Ticker: {ticker}, von: {start_date}, bis: {end_date}, Intervall: {interval}")
        self.status_bar.showMessage(f"Rufe Daten für {ticker} ab...")

        try:
            # Datenabruf im Hintergrund wäre besser für größere Anfragen, hier direkt für Einfachheit
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.current_data_df = fetch_data(ticker, start_date, end_date, interval)
            QApplication.restoreOverrideCursor()

            if self.current_data_df is not None and not self.current_data_df.empty:
                logger.info(f"{len(self.current_data_df)} Datenpunkte für {ticker} geladen.")
                # Um den Index korrekt darzustellen, resetten wir ihn temporär als Spalte
                display_df = self.current_data_df.reset_index()
                model = DataFrameModel(display_df, self)
                self.data_table_view.setModel(model)
                self.data_table_view.resizeColumnsToContents()
                self.status_bar.showMessage(f"Daten für {ticker} erfolgreich geladen.", 5000)

                stock_info = get_stock_info(ticker) # Kann None zurückgeben
                if stock_info and 'longName' in stock_info:
                    self.app_title_label.setText(stock_info['longName'])
                else:
                    self.app_title_label.setText(ticker if ticker else "FinanceTool")

            elif self.current_data_df is not None and self.current_data_df.empty:
                logger.warning(f"Keine Daten für {ticker} im Zeitraum gefunden.")
                QMessageBox.information(self, "Keine Daten", f"Keine Daten für {ticker} im angegebenen Zeitraum gefunden.")
                self.data_table_view.setModel(None)
                self.status_bar.showMessage(f"Keine Daten für {ticker} gefunden.", 5000)
            else:
                raise Exception("fetch_data gab None oder unerwartetes Ergebnis zurück")
        except Exception as e:
            QApplication.restoreOverrideCursor() # Cursor zurücksetzen im Fehlerfall
            logger.error(f"Fehler beim Abrufen oder Anzeigen der Daten für {ticker}: {e}", exc_info=True)
            QMessageBox.critical(self, "Fehler", f"Fehler beim Abrufen der Daten für {ticker}:\n{e}")
            self.data_table_view.setModel(None)
            self.status_bar.showMessage(f"Fehler beim Datenabruf für {ticker}.", 5000)


    def show_indicators_tab(self):
        logger.info("MainWindow.show_indicators_tab: Erstelle/zeige Indikatoren-Tab.")

        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "Indikatoren":
                self.tab_widget.setCurrentIndex(i)
                logger.debug("MainWindow.show_indicators_tab: Wechsle zu existierendem Tab 'Indikatoren'.")
                return

        indicators_widget = QWidget()
        layout = QVBoxLayout(indicators_widget)

        text_area = QTextEdit()
        text_area.setReadOnly(True)

        if not self.available_indicators_info:
            self._load_available_indicators()

        if self.available_indicators_info:
            html_text = "<h1>Verfügbare Indikatoren</h1>"
            for indi in self.available_indicators_info:
                html_text += f"<h2>{indi['name']}</h2>"
                html_text += f"<p><i>{indi['description']}</i></p>"
                html_text += "<b>Parameter:</b><ul>"
                for param in indi['parameters']:
                    html_text += f"<li><b>{param['name']}</b> (Typ: {param['type']}, Default: {param['default']})<br>{param['description']}</li>"
                html_text += "</ul><b>Ausgabefelder:</b> <code>" + ", ".join(indi['output_fields']) + "</code><hr>"
            text_area.setHtml(html_text)
        else:
            text_area.setText("Keine Indikatoreninformationen verfügbar oder geladen.")

        layout.addWidget(text_area)
        self._add_tab(indicators_widget, "Indikatoren")


    def show_strategy_mgmt_tab(self):
        logger.info("MainWindow.show_strategy_mgmt_tab: Erstelle/zeige Strategie-Management-Tab.")

        tab_title = "Strategie Mgmt."
        # Vermeide Duplikate, wenn Button mehrmals geklickt wird
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_title:
                self.tab_widget.setCurrentIndex(i)
                logger.debug(f"MainWindow.show_strategy_mgmt_tab: Wechsle zu existierendem Tab '{tab_title}'.")
                return

        self.strategy_mgmt_widget = QWidget() # Eigene Referenz für späteren Zugriff auf Widgets darin
        layout = QVBoxLayout(self.strategy_mgmt_widget)

        # Bereich zum Laden von Strategien
        load_group = QGroupBox("Strategie Laden/Anzeigen")
        load_layout = QVBoxLayout()

        load_button = QPushButton("Strategie aus JSON laden")
        load_button.clicked.connect(self._load_strategy_action)
        load_layout.addWidget(load_button)

        self.strat_info_area = QTextEdit() # Attribut für Zugriff von _load_strategy_action
        self.strat_info_area.setReadOnly(True)
        self.strat_info_area.setText("Keine Strategie geladen. Bitte eine .json Datei auswählen.")
        self.strat_info_area.setFixedHeight(150)
        load_layout.addWidget(self.strat_info_area)
        load_group.setLayout(load_layout)
        layout.addWidget(load_group)

        # Bereich für Backtesting-Start mit geladener Strategie
        run_backtest_group = QGroupBox("Backtest mit geladener Strategie")
        run_backtest_form_layout = QFormLayout()

        # Eingabefelder für Backtest-Parameter (Ticker, Zeitraum etc.)
        # Initialwerte von Datenabruf-Tab übernehmen, falls vorhanden
        default_ticker = self.df_ticker_edit.text() if hasattr(self, 'df_ticker_edit') and self.df_ticker_edit.text() else "AAPL"
        self.bt_ticker_edit = QLineEdit(default_ticker)

        default_start_date = self.df_start_date_edit.date() if hasattr(self, 'df_start_date_edit') else QDate.currentDate().addYears(-2)
        self.bt_start_date_edit = QDateEdit(default_start_date)
        self.bt_start_date_edit.setCalendarPopup(True)
        self.bt_start_date_edit.setDisplayFormat("yyyy-MM-dd")

        default_end_date = self.df_end_date_edit.date() if hasattr(self, 'df_end_date_edit') else QDate.currentDate()
        self.bt_end_date_edit = QDateEdit(default_end_date)
        self.bt_end_date_edit.setCalendarPopup(True)
        self.bt_end_date_edit.setDisplayFormat("yyyy-MM-dd")

        self.bt_interval_combo = QComboBox()
        self.bt_interval_combo.addItems(["1d", "1wk", "1mo", "1h", "30m", "5m"])
        if hasattr(self, 'df_interval_combo'):
            self.bt_interval_combo.setCurrentText(self.df_interval_combo.currentText())

        self.bt_initial_capital_edit = QLineEdit("10000.0")
        self.bt_commission_edit = QLineEdit("0.0")
        self.bt_slippage_edit = QLineEdit("0.0") # In Prozent, z.B. 0.001 für 0.1%

        run_backtest_form_layout.addRow("Ticker:", self.bt_ticker_edit)
        run_backtest_form_layout.addRow("Startdatum:", self.bt_start_date_edit)
        run_backtest_form_layout.addRow("Enddatum:", self.bt_end_date_edit)
        run_backtest_form_layout.addRow("Intervall:", self.bt_interval_combo)
        run_backtest_form_layout.addRow("Startkapital:", self.bt_initial_capital_edit)
        run_backtest_form_layout.addRow("Kommission/Trade:", self.bt_commission_edit)
        run_backtest_form_layout.addRow("Slippage (z.B. 0.001):", self.bt_slippage_edit)

        self.run_backtest_from_strat_button = QPushButton("Backtest für geladene Strategie starten")
        self.run_backtest_from_strat_button.clicked.connect(self._run_backtest_for_loaded_strategy)
        self.run_backtest_from_strat_button.setEnabled(False) # Aktivieren, wenn Strategie UND Daten geladen
        run_backtest_form_layout.addRow(self.run_backtest_from_strat_button)
        run_backtest_group.setLayout(run_backtest_form_layout)
        layout.addWidget(run_backtest_group)

        layout.addStretch()
        self._add_tab(self.strategy_mgmt_widget, tab_title)

    def _load_strategy_action(self):
        logger.debug("MainWindow._load_strategy_action: Öffne Datei-Dialog zum Laden der Strategie.")
        filepath, _ = QFileDialog.getOpenFileName(self, "Strategie laden", "", "JSON Dateien (*.json);;Alle Dateien (*)")
        if filepath:
            try:
                self.current_strategy_def = load_strategy_from_json(filepath)
                if self.current_strategy_def:
                    logger.info(f"Strategie '{self.current_strategy_def.name}' geladen von {filepath}")
                    self.strat_info_area.setText(
                        f"Strategie Geladen:\n\nName: {self.current_strategy_def.name}\n"
                        f"Beschreibung: {self.current_strategy_def.description}\n"
                        f"Version: {self.current_strategy_def.version}\n"
                        f"Kaufregeln: {len(self.current_strategy_def.buy_rules)}\n"
                        f"Verkaufsregeln: {len(self.current_strategy_def.sell_rules)}"
                    )
                    self.run_backtest_from_strat_button.setEnabled(True) # Button aktivieren
                    self.status_bar.showMessage(f"Strategie '{self.current_strategy_def.name}' geladen.", 5000)
                else:
                    raise ValueError("load_strategy_from_json gab None zurück.") # Sollte nicht passieren, wenn None zurückgegeben wird
            except Exception as e:
                logger.error(f"Fehler beim Laden der Strategie von {filepath}: {e}", exc_info=True)
                QMessageBox.critical(self, "Fehler", f"Konnte Strategie nicht laden:\n{e}")
                self.current_strategy_def = None
                self.strat_info_area.setText("Fehler beim Laden der Strategie.")
                self.run_backtest_from_strat_button.setEnabled(False)
                self.status_bar.showMessage("Fehler beim Laden der Strategie.", 5000)

    def _run_backtest_for_loaded_strategy(self):
        logger.info("MainWindow._run_backtest_for_loaded_strategy: Starte Backtest für geladene Strategie.")
        if not self.current_strategy_def:
            QMessageBox.warning(self, "Keine Strategie", "Bitte zuerst eine Strategie laden.")
            return

        # Hole Parameter aus den UI-Feldern des Strategie-Management-Tabs
        ticker = self.bt_ticker_edit.text()
        start_date = self.bt_start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.bt_end_date_edit.date().toString("yyyy-MM-dd")
        interval = self.bt_interval_combo.currentText()
        try:
            initial_capital = float(self.bt_initial_capital_edit.text())
            commission = float(self.bt_commission_edit.text())
            slippage = float(self.bt_slippage_edit.text())
        except ValueError:
            QMessageBox.critical(self, "Parameterfehler", "Startkapital, Kommission und Slippage müssen gültige Zahlen sein.")
            return

        if not ticker:
            QMessageBox.warning(self, "Ticker fehlt", "Bitte einen Ticker für den Backtest angeben.")
            return

        logger.info(f"Starte Backtest mit: Ticker={ticker}, Start={start_date}, Ende={end_date}, Intervall={interval}, Strategie='{self.current_strategy_def.name}', Kapital={initial_capital}")
        self.status_bar.showMessage(f"Starte Backtest für {self.current_strategy_def.name} auf {ticker}...")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        try:
            # Backtester-Instanz verwenden oder neu erstellen, falls Konfiguration pro Lauf nötig
            # Hier verwenden wir die in __init__ erstellte Instanz und setzen Parameter neu, falls nötig
            # Besser: Backtester nimmt Kapital etc. im Konstruktor an.
            # Für dieses Beispiel: Wir erstellen eine neue Instanz oder konfigurieren die bestehende.
            # Da der Backtester bereits initial_capital etc. im Konstruktor hat, erstellen wir ihn neu.
            # Oder wir machen diese Parameter zu run_backtest Parametern.
            # Ich passe den Backtester an, um Kapital etc. in run_backtest zu akzeptieren.
            # Für jetzt: Annahme, dass der Backtester in __init__ bereits korrekt konfiguriert wurde
            # oder wir erstellen ihn hier neu.

            # Erstelle eine neue Backtester-Instanz mit den aktuellen GUI-Werten
            current_backtester = Backtester(initial_capital=initial_capital, commission_per_trade=commission, slippage_pct=slippage)

            current_backtester.run_backtest(
                ticker=ticker,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                strategy_def=self.current_strategy_def,
                data_pipeline_func=prepare_data_for_strategy,
                strategy_engine_cls=StrategyEvaluator,
                capital_per_trade_pct=0.25 # Beispiel, sollte konfigurierbar sein oder shares_per_trade
            )
            metrics = current_backtester.calculate_performance_metrics()

            QApplication.restoreOverrideCursor()
            self.show_backtesting_tab(metrics=metrics, backtester=current_backtester, ticker_for_plot=ticker) # Übergebe den verwendeten Backtester
            self.status_bar.showMessage(f"Backtest für {self.current_strategy_def.name} abgeschlossen.", 5000)

        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.error(f"Fehler während des Backtests für Strategie '{self.current_strategy_def.name}': {e}", exc_info=True)
            QMessageBox.critical(self, "Backtest Fehler", f"Fehler im Backtest-Prozess:\n{e}")
            self.status_bar.showMessage(f"Fehler im Backtest.", 5000)
            # Zeige leeren Backtest-Tab oder Fehlerinfo im Tab
            self.show_backtesting_tab(metrics={"error": str(e)}, backtester=None, ticker_for_plot=ticker)


    def show_backtesting_tab(self, metrics: Optional[Dict[str, Any]] = None,
                             backtester: Optional[Backtester] = None,
                             ticker_for_plot: Optional[str] = None):
        logger.info("MainWindow.show_backtesting_tab: Erstelle/zeige Backtest-Ergebnisse-Tab.")

        tab_title = "Backtest Ergebnisse"
        existing_tab_index = -1
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == tab_title:
                existing_tab_index = i
                # Alten Inhalt entfernen, bevor neuer hinzugefügt wird
                old_widget = self.tab_widget.widget(i)
                if old_widget:
                    old_widget.deleteLater()
                self.tab_widget.removeTab(i)
                break # Breche Schleife, da Tab neu erstellt wird

        # Erstelle das Widget für den Tab-Inhalt immer neu für sauberen Zustand
        self.backtest_results_widget = QWidget()
        layout = QVBoxLayout(self.backtest_results_widget)

        # Metriken-Anzeige
        metrics_group = QGroupBox("Performance Metriken")
        metrics_layout = QVBoxLayout()
        metrics_text_area = QTextEdit()
        metrics_text_area.setReadOnly(True)

        strat_name_display = "N/A"
        if backtester and backtester.strategy_def: # backtester könnte None sein im Fehlerfall
            strat_name_display = backtester.strategy_def.name
        elif self.current_strategy_def: # Fallback auf die zuletzt global geladene Strategie
             strat_name_display = self.current_strategy_def.name


        if metrics:
            metrics_str = f"Backtest Ergebnisse für '{strat_name_display}' auf {ticker_for_plot or 'N/A'}:\n\n"
            if "error" in metrics:
                 metrics_str += f"  Fehler: {metrics['error']}\n"
                 if "details" in metrics:
                     metrics_str += f"  Details: {metrics['details']}\n"
            else:
                for key, value in metrics.items():
                    metrics_str += f"  {key.replace('_', ' ').capitalize()}: {value}\n"
            metrics_text_area.setText(metrics_str)
        else:
            metrics_text_area.setText("Noch keine Backtest-Ergebnisse vorhanden oder Fehler beim Laden.\nStarten Sie einen Backtest über 'Strategie Mgmt'.")

        metrics_layout.addWidget(metrics_text_area)
        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group, 1)

        # Chart-Anzeige
        chart_group = QGroupBox("Portfolio Entwicklung & Trades")
        chart_layout_container = QVBoxLayout() # Layout für den GroupBox

        # Wichtig: Matplotlib Canvas braucht einen Parent beim Erstellen
        # Wir erstellen einen inneren Widget-Container für den Canvas
        chart_render_widget = QWidget()
        chart_render_layout = QVBoxLayout(chart_render_widget) # Layout für den Canvas selbst

        if backtester and backtester.portfolio_history is not None and not backtester.portfolio_history.empty and \
           backtester.data_with_indicators is not None and not backtester.data_with_indicators.empty:

            if self.mpl_canvas and self.mpl_canvas.parent() is not None:
                 self.mpl_canvas.setParent(None)
                 self.mpl_canvas.deleteLater()

            self.mpl_figure = Figure(figsize=(10, 6), dpi=100) # Angepasste Größe
            ax1 = self.mpl_figure.add_subplot(111)
            ax1.plot(backtester.portfolio_history.index, backtester.portfolio_history['total_value'], label='Portfolio Value', color='blue', lw=1.5)
            ax1.set_xlabel('Datum'); ax1.set_ylabel('Portfolio Wert (€)', color='blue')
            ax1.tick_params(axis='y', labelcolor='blue', labelsize=8)
            ax1.tick_params(axis='x', labelsize=8, rotation=15) # Weniger Rotation für Lesbarkeit
            title_str = f'Portfolio: {strat_name_display}'
            if ticker_for_plot: title_str += f' auf {ticker_for_plot}'
            ax1.set_title(title_str, fontsize=10)
            ax1.grid(True, linestyle='--', alpha=0.6)

            ax2 = ax1.twinx()
            ax2.plot(backtester.data_with_indicators.index, backtester.data_with_indicators['close'], label=f'{ticker_for_plot or "Asset"} Preis', color='grey', alpha=0.5, lw=1)
            ax2.set_ylabel('Preis (€)', color='grey')
            ax2.tick_params(axis='y', labelcolor='grey', labelsize=8)

            if backtester.trades_log is not None and not backtester.trades_log.empty:
                buys = backtester.trades_log[backtester.trades_log['type'] == 'Buy']
                sells = backtester.trades_log[backtester.trades_log['type'] == 'Sell']
                if not buys.empty: ax2.plot(buys['timestamp'], buys['price'], '^', markersize=6, color='green', alpha=0.8, lw=0, label='Kauf')
                if not sells.empty: ax2.plot(sells['timestamp'], sells['price'], 'v', markersize=6, color='red', alpha=0.8, lw=0, label='Verkauf')

            lines, labels = ax1.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax1.legend(lines + lines2, labels + labels2, loc='upper left', fontsize='small')
            self.mpl_figure.tight_layout()

            self.mpl_canvas = FigureCanvasQTAgg(self.mpl_figure)
            chart_render_layout.addWidget(self.mpl_canvas) # Canvas zum inneren Layout hinzufügen
        else:
            no_chart_label = QLabel("Chart-Daten nicht verfügbar oder Backtest fehlgeschlagen.")
            no_chart_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chart_render_layout.addWidget(no_chart_label) # Label zum inneren Layout

        chart_group.setLayout(chart_render_layout) # Inneres Layout dem GroupBox zuweisen
        layout.addWidget(chart_group, 3)

        # Tab hinzufügen oder aktualisieren
        # Da wir den alten Tab (falls vorhanden) oben entfernt haben, fügen wir ihn immer neu hinzu.
        self._add_tab(self.backtest_results_widget, tab_title, switch_to_tab=True)


    def closeEvent(self, event):
        logger.info("MainWindow.closeEvent: Anwendung wird geschlossen.")
        # Hier könnten Speicher- oder Aufräumaktionen vor dem Schließen stattfinden
        super().closeEvent(event)


if __name__ == '__main__':
    # Grundlegendes Logging für den direkten Testlauf von gui.py
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()
    logger.info("Starte PyQt6 Event Loop...")
    sys.exit(app.exec())
