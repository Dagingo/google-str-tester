# finance_tool/strategies.py

import pandas as pd
import numpy as np

class TradingStrategy:
    """
    Basisklasse für Handelsstrategien.
    Jede spezifische Strategie sollte von dieser Klasse erben
    und die Methode `generate_signals` implementieren.
    """
    def __init__(self, data: pd.DataFrame, params: dict = None):
        """
        Initialisiert die Strategie.

        Args:
            data (pd.DataFrame): DataFrame mit historischen Preisdaten (OHLC).
                                 Muss mindestens eine 'Close'-Spalte enthalten.
            params (dict, optional): Dictionary mit Parametern für die Strategie.
        """
        if not isinstance(data, pd.DataFrame):
            raise ValueError("Daten müssen ein Pandas DataFrame sein.")
        if 'Close' not in data.columns:
            raise ValueError("DataFrame muss eine 'Close'-Spalte enthalten.")

        self.data = data.copy() # Kopie erstellen, um Originaldaten nicht zu verändern
        self.params = params if params is not None else {}
        self.signals = None # Wird von generate_signals gefüllt

    def generate_signals(self) -> pd.DataFrame:
        """
        Generiert Handelssignale basierend auf der Strategielogik.
        Diese Methode muss von abgeleiteten Klassen überschrieben werden.

        Returns:
            pd.DataFrame: Ein DataFrame mit einer 'signal'-Spalte (-1 für Short, 0 für Hold, 1 für Long).
                          Der Index sollte mit dem Eingabe-DataFrame übereinstimmen.
        """
        raise NotImplementedError("Die Methode 'generate_signals' muss von der Unterklasse implementiert werden.")

    def _calculate_moving_average(self, window: int, price_type: str = 'Close') -> pd.Series:
        """
        Berechnet einen einfachen gleitenden Durchschnitt (SMA).

        Args:
            window (int): Das Zeitfenster für den gleitenden Durchschnitt.
            price_type (str, optional): Die Spalte, die für die Berechnung verwendet wird (z.B. 'Close', 'Open').
                                        Standard ist 'Close'.

        Returns:
            pd.Series: Eine Pandas Series mit dem gleitenden Durchschnitt.
        """
        if price_type not in self.data.columns:
            raise ValueError(f"Spalte '{price_type}' nicht in den Daten vorhanden.")
        if not isinstance(window, int) or window <= 0:
            raise ValueError("Fenstergröße muss eine positive Ganzzahl sein.")
        return self.data[price_type].rolling(window=window).mean()

    def _calculate_rsi(self, window: int = 14, price_type: str = 'Close') -> pd.Series:
        """
        Berechnet den Relative Strength Index (RSI).

        Args:
            window (int, optional): Das Zeitfenster für den RSI. Standard ist 14.
            price_type (str, optional): Die Spalte, die für die Berechnung verwendet wird. Standard ist 'Close'.

        Returns:
            pd.Series: Eine Pandas Series mit dem RSI.
        """
        if price_type not in self.data.columns:
            raise ValueError(f"Spalte '{price_type}' nicht in den Daten vorhanden.")
        if not isinstance(window, int) or window <= 0:
            raise ValueError("Fenstergröße muss eine positive Ganzzahl sein.")

        delta = self.data[price_type].diff(1)
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)

        avg_gain = gain.rolling(window=window, min_periods=1).mean()
        avg_loss = loss.rolling(window=window, min_periods=1).mean()

        # Vermeide Division durch Null, wenn avg_loss 0 ist
        rs = avg_gain / avg_loss.replace(0, np.nan) # Ersetze 0 durch NaN, um Warnungen zu vermeiden und korrekte Berechnung zu ermöglichen
        rsi = 100 - (100 / (1 + rs))

        # Wenn avg_loss durchgehend 0 war (nur Gewinne), ist RSI 100
        rsi.loc[avg_loss == 0] = 100
        # Wenn avg_gain durchgehend 0 war (nur Verluste), ist RSI 0 (passiert durch rs = 0 -> rsi = 0)
        # Wenn beides 0 ist (keine Preisänderung), ist rs NaN, RSI sollte neutral sein (z.B. 50 oder NaN)
        # Hier wird es durch rs=NaN zu RSI=NaN, was oft als "kein Signal" interpretiert werden kann.
        # Für eine robustere Implementierung bei konstanten Preisen könnte man den RSI auf 50 setzen.
        rsi.fillna(50, inplace=True) # Fülle NaNs, die durch rs=NaN entstanden sind, mit 50

        return rsi

    def _calculate_macd(self, short_window: int = 12, long_window: int = 26, signal_window: int = 9, price_type: str = 'Close') -> tuple[pd.Series, pd.Series, pd.Series]:
        """
        Berechnet den Moving Average Convergence Divergence (MACD).

        Args:
            short_window (int, optional): Kurzes EMA-Fenster. Standard 12.
            long_window (int, optional): Langes EMA-Fenster. Standard 26.
            signal_window (int, optional): EMA-Fenster für die Signallinie. Standard 9.
            price_type (str, optional): Preisspalte. Standard 'Close'.

        Returns:
            tuple[pd.Series, pd.Series, pd.Series]: MACD-Linie, Signallinie, MACD-Histogramm.
        """
        if price_type not in self.data.columns:
            raise ValueError(f"Spalte '{price_type}' nicht in den Daten vorhanden.")

        ema_short = self.data[price_type].ewm(span=short_window, adjust=False).mean()
        ema_long = self.data[price_type].ewm(span=long_window, adjust=False).mean()

        macd_line = ema_short - ema_long
        signal_line = macd_line.ewm(span=signal_window, adjust=False).mean()
        macd_histogram = macd_line - signal_line

        return macd_line, signal_line, macd_histogram

class MovingAverageCrossoverStrategy(TradingStrategy):
    """
    Eine einfache Handelsstrategie basierend auf dem Crossover von zwei gleitenden Durchschnitten.
    """
    def __init__(self, data: pd.DataFrame, params: dict = None):
        """
        Initialisiert die Moving Average Crossover Strategie.

        Args:
            data (pd.DataFrame): DataFrame mit historischen Preisdaten.
            params (dict, optional): Parameter für die Strategie.
                                     Erwartet 'short_window' und 'long_window'.
                                     Defaults: short_window=20, long_window=50.
        """
        super().__init__(data, params)
        self.short_window = self.params.get('short_window', 20)
        self.long_window = self.params.get('long_window', 50)

        if not isinstance(self.short_window, int) or self.short_window <= 0:
            raise ValueError("short_window muss eine positive Ganzzahl sein.")
        if not isinstance(self.long_window, int) or self.long_window <= 0:
            raise ValueError("long_window muss eine positive Ganzzahl sein.")
        if self.short_window >= self.long_window:
            raise ValueError("short_window muss kleiner als long_window sein.")

        self.data[f'SMA_{self.short_window}'] = self._calculate_moving_average(self.short_window)
        self.data[f'SMA_{self.long_window}'] = self._calculate_moving_average(self.long_window)

    def generate_signals(self) -> pd.DataFrame:
        """
        Generiert Handelssignale basierend auf dem MA Crossover.
        - Long-Signal (1): Kurzer MA kreuzt über langen MA.
        - Short-Signal (-1): Kurzer MA kreuzt unter langen MA.
        - Hold-Signal (0): Kein Crossover.

        Returns:
            pd.DataFrame: DataFrame mit 'signal'-Spalte.
        """
        signals_df = pd.DataFrame(index=self.data.index)
        signals_df['signal'] = 0 # Standardmäßig halten

        # Long-Signal: SMA_short kreuzt über SMA_long
        signals_df.loc[self.data[f'SMA_{self.short_window}'] > self.data[f'SMA_{self.long_window}'], 'signal'] = 1

        # Short-Signal: SMA_short kreuzt unter SMA_long
        signals_df.loc[self.data[f'SMA_{self.short_window}'] < self.data[f'SMA_{self.long_window}'], 'signal'] = -1

        # Um nur die Kreuzungspunkte zu bekommen (optional, je nach Backtesting-Logik):
        # signals_df['positions'] = signals_df['signal'].diff()
        # Hier behalten wir das Signal solange die Bedingung erfüllt ist.

        self.signals = signals_df
        return self.signals

class RSIStrategy(TradingStrategy):
    """
    Handelsstrategie basierend auf dem Relative Strength Index (RSI).
    - Long-Signal (1): RSI kreuzt unter die untere Schwelle (überverkauft) und steigt wieder darüber.
    - Short-Signal (-1): RSI kreuzt über die obere Schwelle (überkauft) und fällt wieder darunter.
    """
    def __init__(self, data: pd.DataFrame, params: dict = None):
        """
        Initialisiert die RSI-Strategie.

        Args:
            data (pd.DataFrame): DataFrame mit historischen Preisdaten.
            params (dict, optional): Parameter. Erwartet 'rsi_window', 'rsi_oversold', 'rsi_overbought'.
                                     Defaults: rsi_window=14, rsi_oversold=30, rsi_overbought=70.
        """
        super().__init__(data, params)
        self.rsi_window = self.params.get('rsi_window', 14)
        self.oversold_threshold = self.params.get('rsi_oversold', 30)
        self.overbought_threshold = self.params.get('rsi_overbought', 70)

        if not all(isinstance(p, (int, float)) for p in [self.rsi_window, self.oversold_threshold, self.overbought_threshold]):
            raise ValueError("RSI-Parameter müssen numerisch sein.")
        if self.oversold_threshold >= self.overbought_threshold:
            raise ValueError("rsi_oversold muss kleiner als rsi_overbought sein.")

        self.data['RSI'] = self._calculate_rsi(window=self.rsi_window)

    def generate_signals(self) -> pd.DataFrame:
        """
        Generiert Handelssignale basierend auf RSI-Schwellenwerten.
        - Long (1): Wenn RSI von unter `oversold_threshold` diesen Wert wieder überschreitet.
        - Short (-1): Wenn RSI von über `overbought_threshold` diesen Wert wieder unterschreitet.
        - Hold (0): Sonst.

        Returns:
            pd.DataFrame: DataFrame mit 'signal'-Spalte.
        """
        signals_df = pd.DataFrame(index=self.data.index)
        signals_df['signal'] = 0 # Standardmäßig halten
        rsi = self.data['RSI']

        # Long-Signal: RSI kreuzt von unten die oversold_threshold
        signals_df.loc[(rsi.shift(1) < self.oversold_threshold) & (rsi >= self.oversold_threshold), 'signal'] = 1

        # Short-Signal: RSI kreuzt von oben die overbought_threshold
        signals_df.loc[(rsi.shift(1) > self.overbought_threshold) & (rsi <= self.overbought_threshold), 'signal'] = -1

        # Um Positionen zu halten, bis das Gegensignal kommt (optional)
        # Hier wird nur am Kreuzungstag ein Signal generiert.
        # Für eine Strategie, die Positionen hält:
        # current_signal = 0
        # for i in range(len(signals_df)):
        #     if signals_df['signal'].iloc[i] == 1:
        #         current_signal = 1
        #     elif signals_df['signal'].iloc[i] == -1:
        #         current_signal = -1
        #     signals_df['signal'].iloc[i] = current_signal
        # Diese Logik ist besser im Backtester aufgehoben.

        self.signals = signals_df
        return self.signals

def setup_strategy(strategy_name: str, data: pd.DataFrame, params: dict = None) -> TradingStrategy | None:
    """
    Automatisierte Setup-Funktion für Handelsstrategien.

    Args:
        strategy_name (str): Der Name der zu initialisierenden Strategie (z.B. "MA_Crossover", "RSI").
        data (pd.DataFrame): Die Preisdaten.
        params (dict, optional): Parameter für die Strategie.

    Returns:
        TradingStrategy | None: Eine Instanz der Handelsstrategie oder None bei unbekanntem Namen.
    """
    if strategy_name == "MA_Crossover":
        return MovingAverageCrossoverStrategy(data, params)
    elif strategy_name == "RSI":
        return RSIStrategy(data, params)
    # Weitere Strategien hier hinzufügen
    # elif strategy_name == "MACD":
    #     return MACDStrategy(data, params)
    else:
        print(f"Strategie '{strategy_name}' nicht gefunden.")
        return None

# --- Beispiel für die Verwendung ---
if __name__ == "__main__":
    # Erzeuge Beispieldaten (z.B. von data_fetcher importieren oder manuell erstellen)
    sample_data_dict = {
        'Date': pd.to_datetime(['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04', '2023-01-05',
                                '2023-01-06', '2023-01-07', '2023-01-08', '2023-01-09', '2023-01-10',
                                '2023-01-11', '2023-01-12', '2023-01-13', '2023-01-14', '2023-01-15',
                                '2023-01-16', '2023-01-17', '2023-01-18', '2023-01-19', '2023-01-20',
                                '2023-01-21', '2023-01-22', '2023-01-23', '2023-01-24', '2023-01-25']),
        'Close': [100, 102, 101, 103, 105, 104, 106, 108, 107, 109,
                  110, 108, 107, 105, 103, 100, 98, 100, 102, 104,
                  106, 105, 107, 109, 111]
    }
    sample_df = pd.DataFrame(sample_data_dict)
    sample_df.set_index('Date', inplace=True)
    sample_df['Open'] = sample_df['Close'] - 1 # Dummy Open
    sample_df['High'] = sample_df['Close'] + 1 # Dummy High
    sample_df['Low'] = sample_df['Close'] - 2  # Dummy Low
    sample_df['Volume'] = 1000 # Dummy Volume

    print("--- Beispiel für Moving Average Crossover Strategie ---")
    ma_params = {'short_window': 3, 'long_window': 7}
    ma_strategy_instance = setup_strategy("MA_Crossover", sample_df.copy(), ma_params)

    if ma_strategy_instance:
        ma_signals = ma_strategy_instance.generate_signals()
        print("MA Crossover Strategie Daten mit SMAs:")
        print(ma_strategy_instance.data.tail(10))
        print("\nMA Crossover Signale (letzte 10 Tage):")
        print(ma_signals.tail(10))
        # Zeige, wo Signale generiert wurden (nicht 0)
        print("\nMA Crossover tatsächliche Signaländerungen:")
        print(ma_signals[ma_signals['signal'] != 0].head())


    print("\n--- Beispiel für RSI Strategie ---")
    # Erzeuge Daten, die RSI-Signale auslösen könnten
    rsi_data_dict = {
        'Date': pd.date_range(start='2023-01-01', periods=50, freq='D'),
        'Close': np.concatenate([
            np.linspace(100, 120, 10), # Steigend
            np.linspace(120, 90, 15),  # Fallend (sollte oversold auslösen)
            np.linspace(90, 110, 10),  # Steigend (sollte Kaufsignal auslösen)
            np.linspace(110, 130, 5),  # Stark steigend
            np.linspace(130, 100, 10)  # Fallend (sollte overbought und Verkaufssignal auslösen)
        ])
    }
    rsi_sample_df = pd.DataFrame(rsi_data_dict)
    rsi_sample_df.set_index('Date', inplace=True)

    rsi_params = {'rsi_window': 7, 'rsi_oversold': 30, 'rsi_overbought': 70}
    rsi_strategy_instance = setup_strategy("RSI", rsi_sample_df.copy(), rsi_params)

    if rsi_strategy_instance:
        rsi_signals = rsi_strategy_instance.generate_signals()
        print("RSI Strategie Daten mit RSI:")
        print(rsi_strategy_instance.data.tail(10)) # Zeige einige Datenpunkte
        print("\nRSI Signale (letzte 10 Tage):")
        print(rsi_signals.tail(10))
        # Zeige, wo Signale generiert wurden (nicht 0)
        print("\nRSI tatsächliche Signaländerungen:")
        generated_rsi_signals = rsi_signals[rsi_signals['signal'] != 0]
        if not generated_rsi_signals.empty:
            print(generated_rsi_signals)
        else:
            print("Keine RSI-Signale generiert mit diesen Daten/Parametern.")

    # Testfall für _calculate_macd (nicht Teil einer vollen Strategie hier, nur Test der Funktion)
    print("\n--- Test für MACD Berechnung ---")
    if ma_strategy_instance: # Verwende eine existierende Instanz zum Testen der Hilfsfunktion
        macd_line, signal_line, macd_hist = ma_strategy_instance._calculate_macd()
        print("MACD Linie (letzte 5):")
        print(macd_line.tail())
        print("Signal Linie (letzte 5):")
        print(signal_line.tail())
        print("MACD Histogramm (letzte 5):")
        print(macd_hist.tail())

    print("\n--- Testfall für unbekannte Strategie ---")
    unknown_strategy = setup_strategy("NonExistentStrategy", sample_df.copy())
    if unknown_strategy is None:
        print("Unbekannte Strategie korrekt nicht initialisiert.")

    print("\n--- Testfall für ungültige Parameter (MA Crossover) ---")
    try:
        invalid_ma_params = {'short_window': 5, 'long_window': 3} # short > long
        setup_strategy("MA_Crossover", sample_df.copy(), invalid_ma_params)
    except ValueError as e:
        print(f"Erwarteter Fehler bei MA Crossover mit ungültigen Parametern: {e}")

    try:
        invalid_ma_params_type = {'short_window': 'abc', 'long_window': 10}
        setup_strategy("MA_Crossover", sample_df.copy(), invalid_ma_params_type)
    except ValueError as e:
        print(f"Erwarteter Fehler bei MA Crossover mit ungültigem Typ: {e}")

    print("\n--- Testfall für ungültige Daten (keine 'Close'-Spalte) ---")
    invalid_data_df = pd.DataFrame({'Open': [1,2,3]})
    try:
        setup_strategy("MA_Crossover", invalid_data_df)
    except ValueError as e:
        print(f"Erwarteter Fehler bei ungültigen Daten: {e}")

    print("\n--- Testfall für RSI mit konstanten Preisen ---")
    constant_price_data = pd.DataFrame({
        'Date': pd.date_range(start='2023-01-01', periods=20, freq='D'),
        'Close': [100] * 20
    })
    constant_price_data.set_index('Date', inplace=True)
    rsi_constant_strategy = RSIStrategy(constant_price_data.copy(), {'rsi_window': 5})
    rsi_constant_signals = rsi_constant_strategy.generate_signals()
    print("RSI für konstante Preise (sollte neutral sein, z.B. 50):")
    print(rsi_constant_strategy.data['RSI'].head())
    print("Signale für konstante Preise (sollten 0 sein):")
    print(rsi_constant_signals['signal'].unique())
