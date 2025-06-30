# finance_tool/forward_tester.py

import time
import pandas as pd
from .strategies import TradingStrategy
from .data_fetcher import fetch_data # To get latest data for simulation

class ForwardTester:
    """
    Simuliert Paper Trading für Handelsstrategien mit (simulierten) Echtzeitdaten.
    """
    def __init__(self, strategy_setup_func, strategy_params: dict,
                 ticker_symbol: str, initial_capital: float = 100000.0,
                 commission_per_trade: float = 0.0, slippage_pct: float = 0.0,
                 shares_per_trade: int = None, capital_per_trade_pct: float = None):
        """
        Initialisiert den ForwardTester.

        Args:
            strategy_setup_func (callable): Eine Funktion, die eine Strategie-Instanz zurückgibt
                                            (z.B. finance_tool.strategies.setup_strategy).
                                            Sie muss (strategy_name, data, params) als Argumente akzeptieren.
            strategy_params (dict): Parameter für die zu initialisierende Strategie,
                                    inklusive 'name' der Strategie.
            ticker_symbol (str): Das Tickersymbol für das Paper Trading.
            initial_capital (float): Anfängliches Kapital.
            commission_per_trade (float): Kommission pro Trade.
            slippage_pct (float): Slippage pro Trade in Prozent.
            shares_per_trade (int, optional): Anzahl der Aktien pro Trade.
            capital_per_trade_pct (float, optional): Kapitalanteil pro Trade.
        """
        if not callable(strategy_setup_func):
            raise ValueError("strategy_setup_func muss eine aufrufbare Funktion sein.")
        if 'name' not in strategy_params:
            raise ValueError("strategy_params muss einen 'name' der Strategie enthalten.")
        if (shares_per_trade is None and capital_per_trade_pct is None) or \
           (shares_per_trade is not None and capital_per_trade_pct is not None):
            raise ValueError("Entweder 'shares_per_trade' oder 'capital_per_trade_pct' muss angegeben werden.")

        self.strategy_setup_func = strategy_setup_func
        self.strategy_params = strategy_params
        self.ticker_symbol = ticker_symbol
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.shares = 0.0
        self.portfolio_value = initial_capital
        self.commission_per_trade = commission_per_trade
        self.slippage_pct = slippage_pct
        self.shares_per_trade = shares_per_trade
        self.capital_per_trade_pct = capital_per_trade_pct

        self.historical_data = pd.DataFrame() # Wird mit neuen Daten aktualisiert
        self.strategy_instance = None
        self.current_position = 0 # 0: neutral, 1: long, -1: short
        self.log = [] # Liste für Logging von Aktionen

        print(f"ForwardTester für {self.ticker_symbol} initialisiert mit {self.strategy_params['name']}.")
        self._log_event(f"Initial capital: {self.initial_capital:.2f}")

    def _log_event(self, message: str):
        timestamp = pd.Timestamp.now()
        self.log.append(f"{timestamp} - {message}")
        print(message)

    def _apply_slippage(self, price: float, signal_type: str) -> float:
        """Wendet Slippage an. signal_type: 'buy' oder 'sell'."""
        if signal_type == 'buy':
            return price * (1 + self.slippage_pct)
        elif signal_type == 'sell':
            return price * (1 - self.slippage_pct)
        return price

    def _update_historical_data(self, new_data_point: pd.Series):
        """Fügt einen neuen Datenpunkt zu den historischen Daten hinzu."""
        # Sicherstellen, dass der Index ein DatetimeIndex ist
        if not isinstance(self.historical_data.index, pd.DatetimeIndex):
             self.historical_data.index = pd.to_datetime(self.historical_data.index)

        new_data_df = new_data_point.to_frame().T
        if not isinstance(new_data_df.index, pd.DatetimeIndex):
            new_data_df.index = pd.to_datetime(new_data_df.index)

        self.historical_data = pd.concat([self.historical_data, new_data_df])
        # Halte die Datenmenge begrenzt, um Speicher zu sparen (optional)
        # self.historical_data = self.historical_data.tail(500) # z.B. die letzten 500 Punkte

    def _reinitialize_strategy(self):
        """Initialisiert die Strategie neu mit den aktuellen historischen Daten."""
        if not self.historical_data.empty:
            self.strategy_instance = self.strategy_setup_func(
                strategy_name=self.strategy_params['name'],
                data=self.historical_data.copy(), # Wichtig: Kopie übergeben
                params=self.strategy_params
            )
            if self.strategy_instance is None:
                self._log_event(f"Fehler: Strategie {self.strategy_params['name']} konnte nicht initialisiert werden.")
                raise RuntimeError(f"Strategie {self.strategy_params['name']} konnte nicht initialisiert werden.")
        else:
            self._log_event("Warnung: Keine historischen Daten zum Initialisieren der Strategie.")


    def process_new_data(self, new_price_data: pd.Series):
        """
        Verarbeitet einen neuen Datenpunkt (z.B. einen neuen Kerzenschluss).

        Args:
            new_price_data (pd.Series): Ein Pandas Series mit den neuesten Preisdaten.
                                        Muss mindestens 'Close' und einen Zeitstempel als Namen haben.
                                        Beispiel: pd.Series({'Close': 150.00, 'Open': 149.0, ...}, name=pd.Timestamp.now())
        """
        if not isinstance(new_price_data, pd.Series) or 'Close' not in new_price_data:
            self._log_event("Fehler: new_price_data muss ein pd.Series mit 'Close'-Preis sein.")
            return

        current_price = new_price_data['Close']
        self._log_event(f"Neuer Datenpunkt erhalten: {new_price_data.name} - Close: {current_price:.2f}")

        self._update_historical_data(new_price_data)
        self._reinitialize_strategy() # Strategie mit neuesten Daten aktualisieren

        if self.strategy_instance is None:
            self._log_event("Strategie nicht initialisiert, Verarbeitung übersprungen.")
            return

        signals_df = self.strategy_instance.generate_signals()
        if signals_df.empty:
            self._log_event("Keine Signale von der Strategie generiert.")
            return

        latest_signal = signals_df['signal'].iloc[-1]
        self._log_event(f"Aktuelles Signal von Strategie: {latest_signal}")

        # Trade-Logik (ähnlich wie im Backtester, aber für einzelne Events)
        # Long Signal
        if latest_signal == 1 and self.current_position != 1:
            if self.current_position == -1: # Short-Position schließen
                buy_price_cover = self._apply_slippage(current_price, 'buy')
                cost_cover = self.shares * buy_price_cover # shares ist negativ
                self.cash += cost_cover - self.commission_per_trade
                self._log_event(f"Short-Position ({self.shares} Aktien) geschlossen zu {buy_price_cover:.2f}. Cash: {self.cash:.2f}")
                self.shares = 0.0

            # Long-Position eröffnen
            num_shares_to_buy = 0
            if self.shares_per_trade:
                num_shares_to_buy = self.shares_per_trade
            elif self.capital_per_trade_pct:
                capital_for_trade = self.cash * self.capital_per_trade_pct
                num_shares_to_buy = int(capital_for_trade / self._apply_slippage(current_price, 'buy'))

            if num_shares_to_buy > 0 and self.cash >= num_shares_to_buy * self._apply_slippage(current_price, 'buy') + self.commission_per_trade:
                buy_price = self._apply_slippage(current_price, 'buy')
                cost = num_shares_to_buy * buy_price + self.commission_per_trade
                self.cash -= cost
                self.shares += num_shares_to_buy
                self.current_position = 1
                self._log_event(f"Long-Position eröffnet: {num_shares_to_buy} Aktien gekauft zu {buy_price:.2f}. Cash: {self.cash:.2f}")
            else:
                self._log_event(f"Nicht genügend Kapital oder Shares für Long-Trade. Cash: {self.cash:.2f}, Shares to buy: {num_shares_to_buy}")

        # Short Signal
        elif latest_signal == -1 and self.current_position != -1:
            if self.current_position == 1: # Long-Position schließen
                sell_price_close = self._apply_slippage(current_price, 'sell')
                proceeds_close = self.shares * sell_price_close - self.commission_per_trade
                self.cash += proceeds_close
                self._log_event(f"Long-Position ({self.shares} Aktien) geschlossen zu {sell_price_close:.2f}. Cash: {self.cash:.2f}")
                self.shares = 0.0

            # Short-Position eröffnen
            num_shares_to_short = 0
            if self.shares_per_trade:
                num_shares_to_short = self.shares_per_trade
            elif self.capital_per_trade_pct:
                nominal_value_to_short = self.portfolio_value * self.capital_per_trade_pct # Portfolio-Wert als Basis
                num_shares_to_short = int(nominal_value_to_short / self._apply_slippage(current_price, 'sell'))

            if num_shares_to_short > 0:
                sell_price_short = self._apply_slippage(current_price, 'sell')
                proceeds_short = num_shares_to_short * sell_price_short - self.commission_per_trade
                self.cash += proceeds_short
                self.shares -= num_shares_to_short # Negative Aktien
                self.current_position = -1
                self._log_event(f"Short-Position eröffnet: {num_shares_to_short} Aktien geshortet zu {sell_price_short:.2f}. Cash: {self.cash:.2f}")
            else:
                 self._log_event(f"Keine Shares für Short-Trade. Shares to short: {num_shares_to_short}")


        # Neutral Signal (Position schließen)
        elif latest_signal == 0 and self.current_position != 0:
            if self.current_position == 1: # Long schließen
                sell_price = self._apply_slippage(current_price, 'sell')
                self.cash += self.shares * sell_price - self.commission_per_trade
                self._log_event(f"Long-Position ({self.shares} Aktien) neutralisiert zu {sell_price:.2f}. Cash: {self.cash:.2f}")
            elif self.current_position == -1: # Short schließen
                buy_price = self._apply_slippage(current_price, 'buy')
                self.cash += self.shares * buy_price - self.commission_per_trade # shares ist negativ
                self._log_event(f"Short-Position ({self.shares} Aktien) neutralisiert zu {buy_price:.2f}. Cash: {self.cash:.2f}")
            self.shares = 0.0
            self.current_position = 0

        # Portfolio-Wert aktualisieren
        self.portfolio_value = self.cash + self.shares * current_price
        self._log_event(f"Portfolio-Wert aktualisiert: {self.portfolio_value:.2f} (Cash: {self.cash:.2f}, Holdings: {self.shares * current_price:.2f}, Shares: {self.shares})")

    def run_simulation_loop(self, data_feed_func, interval_seconds: int = 60, run_duration_seconds: int = 300):
        """
        Startet eine Simulationsschleife, die periodisch neue Daten abruft und verarbeitet.

        Args:
            data_feed_func (callable): Eine Funktion, die den neuesten Preis als pd.Series zurückgibt.
                                       Diese Funktion sollte den Ticker-Symbol kennen oder übergeben bekommen.
                                       z.B. `lambda: get_latest_simulated_price(self.ticker_symbol)`
            interval_seconds (int): Intervall in Sekunden, in dem neue Daten abgerufen werden.
            run_duration_seconds (int): Gesamtdauer der Simulation in Sekunden.
        """
        self._log_event(f"Starte Forward-Testing-Simulation für {run_duration_seconds} Sekunden (Intervall: {interval_seconds}s).")
        start_time = time.time()

        # Initialisiere mit einigen historischen Daten, falls vorhanden, um die Strategie beim ersten Mal zu füttern
        # Hier laden wir z.B. die Daten der letzten Tage, um die Indikatoren zu initialisieren
        # Dies ist wichtig, damit Indikatoren wie MA nicht bei Null anfangen.
        try:
            # Lade z.B. die letzten 60 Tage an täglichen Daten, um Indikatoren vorzubereiten
            # Die Intervallwahl hängt von der Strategie ab. Wenn die Strategie auf Intraday-Daten basiert,
            # dann sollten hier auch Intraday-Daten geladen werden.
            end_date_hist = pd.Timestamp.now().strftime('%Y-%m-%d')
            start_date_hist = (pd.Timestamp.now() - pd.Timedelta(days=90)).strftime('%Y-%m-%d') # z.B. 90 Tage

            self._log_event(f"Lade initiale historische Daten ({start_date_hist} bis {end_date_hist}) für {self.ticker_symbol}...")
            initial_hist_data = fetch_data(self.ticker_symbol, start_date_hist, end_date_hist, interval="1d") # Oder "1h" etc.

            if initial_hist_data is not None and not initial_hist_data.empty:
                self.historical_data = initial_hist_data.copy()
                self._reinitialize_strategy()
                self._log_event(f"{len(self.historical_data)} initiale historische Datenpunkte geladen.")
            else:
                self._log_event("Keine initialen historischen Daten geladen.")
        except Exception as e:
            self._log_event(f"Fehler beim Laden initialer historischer Daten: {e}")


        while time.time() - start_time < run_duration_seconds:
            new_data = data_feed_func() # Ruft die externe Funktion auf, um neue Daten zu erhalten
            if new_data is not None:
                self.process_new_data(new_data)
            else:
                self._log_event("Keine neuen Daten vom Feed erhalten.")

            # Warte bis zum nächsten Intervall
            time.sleep(interval_seconds)

        self._log_event("Forward-Testing-Simulation beendet.")
        self.summarize_performance()

    def summarize_performance(self):
        """Gibt eine Zusammenfassung der Performance aus."""
        self._log_event("\n--- Performance Zusammenfassung ---")
        self._log_event(f"Startkapital: {self.initial_capital:.2f}")
        self.portfolio_value = self.cash + self.shares * (self.historical_data['Close'].iloc[-1] if not self.historical_data.empty and self.shares != 0 else 0)
        self._log_event(f"Endkapital: {self.portfolio_value:.2f}")
        total_return = (self.portfolio_value - self.initial_capital) / self.initial_capital * 100
        self._log_event(f"Gesamtrendite: {total_return:.2f}%")
        self._log_event(f"Anzahl der geloggten Events/Trades: {len(self.log) - (1 + 3 +1)}") # Abzüglich Start/Ende Logs etc.

# --- Beispiel für die Verwendung ---

# Globale Variable für simulierte Preisdaten (nur für dieses Beispiel)
simulated_price_history = []
simulated_start_price = 150.0

def get_latest_simulated_price(ticker: str, step: int) -> pd.Series | None:
    """
    Simuliert einen Datenfeed, der neue Preisdaten liefert.
    In einer echten Anwendung wäre dies eine Verbindung zu einer Börsen-API.
    """
    global simulated_start_price, simulated_price_history
    # Simuliere eine kleine Preisänderung
    change = np.random.uniform(-0.5, 0.5) + np.sin(step / 10) * 0.3 # Kleine Schwankung + Sinus-Welle
    new_price = simulated_start_price + change
    simulated_start_price = new_price # Update für den nächsten Schritt

    # Stelle sicher, dass der Preis nicht negativ wird
    new_price = max(0.01, new_price)

    timestamp = pd.Timestamp.now()
    # Erzeuge OHLCV Daten (hier vereinfacht)
    data_point = pd.Series({
        'Open': new_price - np.random.uniform(0, 0.1),
        'High': new_price + np.random.uniform(0, 0.1),
        'Low': new_price - np.random.uniform(0, 0.1),
        'Close': new_price,
        'Volume': np.random.randint(1000, 5000)
    }, name=timestamp)

    simulated_price_history.append(data_point)
    # print(f"[SIM_FEED] {ticker}: Generated new price {new_price:.2f} at {timestamp}")
    return data_point

if __name__ == "__main__":
    # Temporäre Anpassung für direkten Skriptaufruf
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import numpy as np # Für die Simulation
    from finance_tool.strategies import setup_strategy # Importiere die Setup-Funktion

    print("--- Starte Forward Tester Beispiel ---")

    # Parameter für die Strategie (z.B. MA Crossover)
    ma_params_ft = {
        'name': 'MA_Crossover', # Name der Strategie, wie in setup_strategy erwartet
        'short_window': 5,    # Kürzere Fenster für schnellere Reaktion im Test
        'long_window': 12
    }

    # Initialisiere den ForwardTester
    # Wir verwenden hier capital_per_trade_pct
    forward_tester_ma = ForwardTester(
        strategy_setup_func=setup_strategy,
        strategy_params=ma_params_ft,
        ticker_symbol="SIMULATED_STOCK",
        initial_capital=10000.0,
        commission_per_trade=1.0, # Geringe Kommission
        slippage_pct=0.0005,       # Geringe Slippage
        capital_per_trade_pct=0.25 # 25% des Kapitals pro Trade
    )

    # Starte die Simulationsschleife
    # Wir brauchen eine Möglichkeit, den `step` in `get_latest_simulated_price` zu inkrementieren.
    # Wir können `data_feed_func` als Lambda mit einem veränderlichen Argument erstellen
    # oder eine Klasse verwenden, um den Zustand zu halten.

    class SimulatedFeed:
        def __init__(self, ticker):
            self.ticker = ticker
            self.step = 0

        def get_price(self):
            price_data = get_latest_simulated_price(self.ticker, self.step)
            self.step += 1
            return price_data

    sim_feed = SimulatedFeed(ticker="SIMULATED_STOCK")

    # Kurze Simulation für das Beispiel: 60 Sekunden Laufzeit, 5-Sekunden-Intervall
    try:
        forward_tester_ma.run_simulation_loop(
            data_feed_func=sim_feed.get_price,
            interval_seconds=5,
            run_duration_seconds=60
        )
    except Exception as e:
        print(f"Ein Fehler ist während der Simulation aufgetreten: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Log des Forward Testers ---")
    for entry in forward_tester_ma.log[-15:]: # Zeige die letzten 15 Log-Einträge
        print(entry)

    print("\nSimulierte Preishistorie (erste 5 und letzte 5 Punkte):")
    if simulated_price_history:
        temp_df = pd.DataFrame(simulated_price_history)
        print(temp_df.head())
        print("...")
        print(temp_df.tail())
    else:
        print("Keine simulierten Preisdaten erzeugt.")

    print("\n--- Forward Tester Beispiel Ende ---")
