# finance_tool/indicators.py
import pandas as pd
import pandas_ta as ta
import inspect
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Type, Tuple

logger = logging.getLogger(__name__)

class IndicatorParameter:
    """Beschreibt einen Parameter für einen technischen Indikator."""
    def __init__(self, name: str, param_type: Type, default_value: Any, description: str = ""):
        self.name = name
        self.param_type = param_type
        self.default_value = default_value
        self.description = description

    def __repr__(self):
        return f"IndicatorParameter(name='{self.name}', type={self.param_type.__name__}, default={self.default_value})"

class TechnicalIndicator(ABC):
    """
    Abstrakte Basisklasse für technische Indikatoren.
    """
    # Diese Klassenattribute sollten von Unterklassen überschrieben werden
    name: str = "Base Indicator"
    description: str = "This is a base class and should not be used directly."
    parameters: List[IndicatorParameter] = []
    output_field_names: List[str] = [] # Namen der Spalten, die der Indikator erzeugt

    def __init__(self, **kwargs):
        """
        Initialisiert den Indikator mit spezifischen Parametern.
        kwargs werden verwendet, um die in `parameters` definierten Standardwerte zu überschreiben.
        """
        self.current_params = {}
        for param_def in self.parameters:
            self.current_params[param_def.name] = kwargs.get(param_def.name, param_def.default_value)
        logger.debug(f"TechnicalIndicator '{self.name}' initialisiert mit Parametern: {self.current_params}")

    @abstractmethod
    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Berechnet den Indikator und fügt die Ergebnisse zum DataFrame hinzu.
        Die Eingabedaten (data) sollten mindestens 'high', 'low', 'close', 'open', 'volume' Spalten enthalten,
        abhängig von den Anforderungen des Indikators.

        Args:
            data (pd.DataFrame): Eingabe-DataFrame mit Preisdaten.

        Returns:
            pd.DataFrame: DataFrame mit den zusätzlichen Spalten für die Indikatorwerte.
                          Die Spaltennamen sollten mit `output_field_names` übereinstimmen.
        """
        pass

    @classmethod
    def get_info(cls) -> Dict[str, Any]:
        """Gibt Informationen über den Indikator zurück."""
        return {
            "name": cls.name,
            "description": cls.description,
            "parameters": [{"name": p.name, "type": p.param_type.__name__, "default": p.default_value, "description": p.description} for p in cls.parameters],
            "output_fields": cls.output_field_names
        }

# --- Beispiel-Indikatoren ---

class SMAIndicator(TechnicalIndicator):
    name = "SMA"
    description = "Simple Moving Average."
    parameters = [
        IndicatorParameter(name="length", param_type=int, default_value=20, description="The time period.")
    ]
    # pandas_ta benennt die Spalte automatisch (z.B. SMA_20). Wir standardisieren hier.
    output_field_names = ["sma"]

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        length = self.current_params.get("length", 20)
        if length <= 0:
            logger.warning(f"{self.name}: Ungültige Länge {length}, verwende Default 20.")
            length = 20

        # Stelle sicher, dass 'close' vorhanden ist
        if 'close' not in data.columns:
            logger.error(f"{self.name}: 'close' Spalte nicht in Daten vorhanden.")
            # Füge leere Spalten hinzu, um Fehler zu vermeiden, aber signalisiere das Problem
            for field in self.output_field_names:
                data[field] = pd.NA
            return data

        # pandas_ta erzeugt Spaltennamen wie SMA_length, z.B. SMA_20
        # Wir benennen sie um oder extrahieren sie entsprechend output_field_names
        try:
            data.ta.sma(length=length, append=True)
            # Der tatsächliche Spaltenname, den pandas_ta erzeugt
            generated_col_name = f"SMA_{length}"
            if generated_col_name in data.columns:
                # Benenne die Spalte um, um unserem output_field_names zu entsprechen
                # Hier nehmen wir an, dass es nur ein Output-Feld gibt.
                # Bei mehreren Feldern wäre eine Mapping-Logik nötig.
                if len(self.output_field_names) == 1:
                    data[self.output_field_names[0]] = data[generated_col_name]
                    if self.output_field_names[0] != generated_col_name: # Lösche Original nur wenn umbenannt
                         data.drop(columns=[generated_col_name], inplace=True)
                else: # Komplexerer Fall, hier nicht vollständig behandelt
                    logger.warning(f"{self.name}: Mehrere output_field_names definiert, aber pandas_ta generiert nur eine Spalte. Anpassung erforderlich.")
            else:
                logger.error(f"{self.name}: pandas_ta hat die erwartete Spalte '{generated_col_name}' nicht erstellt.")
                for field in self.output_field_names: data[field] = pd.NA
        except Exception as e:
            logger.error(f"{self.name}: Fehler bei der Berechnung mit pandas_ta: {e}", exc_info=True)
            for field in self.output_field_names: data[field] = pd.NA
        return data

class EMAIndicator(TechnicalIndicator):
    name = "EMA"
    description = "Exponential Moving Average."
    parameters = [
        IndicatorParameter(name="length", param_type=int, default_value=20, description="The time period.")
    ]
    output_field_names = ["ema"]

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        length = self.current_params.get("length", 20)
        if length <= 0: length = 20
        if 'close' not in data.columns:
            logger.error(f"{self.name}: 'close' Spalte nicht in Daten vorhanden.")
            for field in self.output_field_names: data[field] = pd.NA
            return data
        try:
            data.ta.ema(length=length, append=True)
            generated_col_name = f"EMA_{length}"
            if generated_col_name in data.columns and len(self.output_field_names) == 1:
                data[self.output_field_names[0]] = data[generated_col_name]
                if self.output_field_names[0] != generated_col_name:
                    data.drop(columns=[generated_col_name], inplace=True)
            elif generated_col_name not in data.columns:
                 logger.error(f"{self.name}: pandas_ta hat die erwartete Spalte '{generated_col_name}' nicht erstellt.")
                 for field in self.output_field_names: data[field] = pd.NA
        except Exception as e:
            logger.error(f"{self.name}: Fehler bei der Berechnung mit pandas_ta: {e}", exc_info=True)
            for field in self.output_field_names: data[field] = pd.NA
        return data


class RSIIndicator(TechnicalIndicator):
    name = "RSI"
    description = "Relative Strength Index."
    parameters = [
        IndicatorParameter(name="length", param_type=int, default_value=14, description="The time period for RSI calculation.")
    ]
    output_field_names = ["rsi"] # pandas_ta nennt es RSI_length

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        length = self.current_params.get("length", 14)
        if length <= 0: length = 14
        if 'close' not in data.columns:
            logger.error(f"{self.name}: 'close' Spalte nicht in Daten vorhanden.")
            for field in self.output_field_names: data[field] = pd.NA
            return data
        try:
            data.ta.rsi(length=length, append=True)
            generated_col_name = f"RSI_{length}"
            if generated_col_name in data.columns and len(self.output_field_names) == 1:
                data[self.output_field_names[0]] = data[generated_col_name]
                if self.output_field_names[0] != generated_col_name:
                    data.drop(columns=[generated_col_name], inplace=True)
            elif generated_col_name not in data.columns:
                 logger.error(f"{self.name}: pandas_ta hat die erwartete Spalte '{generated_col_name}' nicht erstellt.")
                 for field in self.output_field_names: data[field] = pd.NA
        except Exception as e:
            logger.error(f"{self.name}: Fehler bei der Berechnung mit pandas_ta: {e}", exc_info=True)
            for field in self.output_field_names: data[field] = pd.NA
        return data

class MACDIndicator(TechnicalIndicator):
    name = "MACD"
    description = "Moving Average Convergence Divergence."
    parameters = [
        IndicatorParameter(name="fast", param_type=int, default_value=12, description="Fast EMA period."),
        IndicatorParameter(name="slow", param_type=int, default_value=26, description="Slow EMA period."),
        IndicatorParameter(name="signal", param_type=int, default_value=9, description="Signal EMA period.")
    ]
    # pandas_ta erzeugt MACD_12_26_9, MACDh_12_26_9, MACDs_12_26_9
    output_field_names = ["macd_line", "macd_histogram", "macd_signal"]

    def calculate(self, data: pd.DataFrame) -> pd.DataFrame:
        fast = self.current_params.get("fast", 12)
        slow = self.current_params.get("slow", 26)
        signal = self.current_params.get("signal", 9)
        if 'close' not in data.columns:
            logger.error(f"{self.name}: 'close' Spalte nicht in Daten vorhanden.")
            for field in self.output_field_names: data[field] = pd.NA
            return data

        try:
            data.ta.macd(fast=fast, slow=slow, signal=signal, append=True)
            # Erwartete Spalten von pandas_ta
            base_name = f"{fast}_{slow}_{signal}"
            expected_cols_map = {
                f"MACD_{base_name}": "macd_line",
                f"MACDh_{base_name}": "macd_histogram",
                f"MACDs_{base_name}": "macd_signal"
            }

            cols_to_drop = []
            for pta_col, our_col in expected_cols_map.items():
                if pta_col in data.columns:
                    if our_col in self.output_field_names:
                        data[our_col] = data[pta_col]
                        if pta_col != our_col: # Nur löschen, wenn der Name anders ist
                            cols_to_drop.append(pta_col)
                    else:
                        logger.warning(f"{self.name}: pandas_ta Spalte '{pta_col}' hat kein Mapping in output_field_names.")
                        cols_to_drop.append(pta_col) # Unbenötigte Spalte löschen
                else:
                    logger.error(f"{self.name}: pandas_ta hat die erwartete Spalte '{pta_col}' nicht erstellt.")
                    if our_col in self.output_field_names: data[our_col] = pd.NA # Fehlende Spalte mit NA füllen

            if cols_to_drop:
                data.drop(columns=cols_to_drop, inplace=True, errors='ignore')

        except Exception as e:
            logger.error(f"{self.name}: Fehler bei der Berechnung mit pandas_ta: {e}", exc_info=True)
            for field in self.output_field_names: data[field] = pd.NA
        return data


# --- Indikator-Registrierung und -Management ---
_INDICATORS_REGISTRY: Dict[str, Type[TechnicalIndicator]] = {}

def register_indicator(name: str):
    """
    Ein Dekorator, um Indikator-Klassen automatisch zu registrieren.
    Der Name im Dekorator sollte dem `name`-Attribut der Klasse entsprechen.
    """
    def decorator(cls: Type[TechnicalIndicator]):
        if not issubclass(cls, TechnicalIndicator):
            raise TypeError(f"Klasse {cls.__name__} ist kein TechnicalIndicator.")
        if name in _INDICATORS_REGISTRY:
            logger.warning(f"Indikator '{name}' wird überschrieben.")
        _INDICATORS_REGISTRY[name] = cls
        logger.debug(f"Indikator '{name}' (Klasse {cls.__name__}) registriert.")
        return cls
    return decorator

def discover_indicators(module_name: str = __name__):
    """
    Durchsucht das angegebene Modul nach Klassen, die von TechnicalIndicator erben
    und registriert sie, falls sie noch nicht über den Dekorator registriert wurden.
    Diese Funktion ist nützlich, wenn Indikatoren nicht explizit mit @register_indicator
    versehen sind oder um sicherzustellen, dass alle geladenen Indikatoren bekannt sind.
    """
    current_module = sys.modules[module_name]
    for name, obj in inspect.getmembers(current_module):
        if inspect.isclass(obj) and issubclass(obj, TechnicalIndicator) and obj is not TechnicalIndicator:
            # Verwende das 'name' Attribut der Klasse für die Registrierung
            indicator_name = getattr(obj, 'name', None)
            if indicator_name and indicator_name not in _INDICATORS_REGISTRY :
                _INDICATORS_REGISTRY[indicator_name] = obj
                logger.debug(f"Indikator '{indicator_name}' (Klasse {obj.__name__}) durch Discovery registriert.")
            elif not indicator_name:
                 logger.warning(f"Klasse {obj.__name__} erbt von TechnicalIndicator, hat aber kein 'name' Attribut für die Registrierung.")


def get_indicator_class(name: str) -> Type[TechnicalIndicator] | None:
    return _INDICATORS_REGISTRY.get(name)

def get_available_indicators() -> List[Dict[str, Any]]:
    """Gibt eine Liste mit Informationen über alle registrierten Indikatoren zurück."""
    return [cls.get_info() for cls in _INDICATORS_REGISTRY.values()]

# Registriere die oben definierten Indikatoren explizit oder durch Discovery
# Explizite Registrierung ist oft klarer:
_INDICATORS_REGISTRY[SMAIndicator.name] = SMAIndicator
_INDICATORS_REGISTRY[EMAIndicator.name] = EMAIndicator
_INDICATORS_REGISTRY[RSIIndicator.name] = RSIIndicator
_INDICATORS_REGISTRY[MACDIndicator.name] = MACDIndicator
# Alternativ könnte man discover_indicators() aufrufen, nachdem alle Klassen definiert sind.
# discover_indicators() # Würde die oben genannten auch finden, wenn sie nicht explizit registriert wären.


if __name__ == "__main__":
    import sys # Importiere sys für logging.StreamHandler und discover_indicators
    # Logging-Setup für den Testlauf
    if not logging.getLogger().hasHandlers(): # Nur wenn nicht schon von main.py konfiguriert
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    logger.info("--- Test des Indikatoren-Moduls ---")

    # Beispiel-Daten erstellen (normalerweise von data_fetcher)
    num_points = 100 # Mehr Datenpunkte für stabilere Indikatorberechnung
    prices = [10 + i * 0.5 + (i//10) * (i%5) for i in range(num_points)] # Einfache Preisreihe mit etwas Variation
    sample_data = {
        'open': [p - 0.2 for p in prices],
        'high': [p + 0.3 for p in prices],
        'low': [p - 0.3 for p in prices],
        'close': prices,
        'volume': [100 + i * 10 for i in range(num_points)]
    }
    df = pd.DataFrame(sample_data)
    # pandas_ta benötigt manchmal einen DatetimeIndex
    df.index = pd.to_datetime(pd.date_range(start='2023-01-01', periods=len(df)))


    logger.info("\nVerfügbare Indikatoren:")
    available_inds = get_available_indicators()
    for ind_info in available_inds:
        logger.info(f"  Name: {ind_info['name']}, Beschreibung: {ind_info['description']}")
        logger.info(f"    Parameter: {ind_info['parameters']}")
        logger.info(f"    Ausgabefelder: {ind_info['output_fields']}")

    # Teste SMA
    logger.info("\n--- Test SMAIndicator ---")
    sma_cls = get_indicator_class("SMA")
    if sma_cls:
        sma_indicator = sma_cls(length=5) # Parameter überschreiben
        df_sma = sma_indicator.calculate(df.copy()) # Kopie übergeben, um Original-df nicht zu ändern
        logger.info("Daten mit SMA (letzte 5 Zeilen):")
        logger.info(df_sma[['close', sma_indicator.output_field_names[0]]].tail())

    # Teste RSI
    logger.info("\n--- Test RSIIndicator ---")
    rsi_cls = get_indicator_class("RSI")
    if rsi_cls:
        rsi_indicator = rsi_cls(length=7)
        df_rsi = rsi_indicator.calculate(df.copy())
        logger.info("Daten mit RSI (letzte 5 Zeilen):")
        logger.info(df_rsi[['close', rsi_indicator.output_field_names[0]]].tail())

    # Teste MACD
    logger.info("\n--- Test MACDIndicator ---")
    macd_cls = get_indicator_class("MACD")
    if macd_cls:
        macd_indicator = macd_cls(fast=8, slow=18, signal=6) # Angepasste Parameter
        df_macd = macd_indicator.calculate(df.copy())
        logger.info("Daten mit MACD (letzte 5 Zeilen):")
        logger.info(df_macd[['close'] + macd_indicator.output_field_names].tail())

    logger.info("\n--- Test Indikator mit Default-Parametern ---")
    ema_cls = get_indicator_class("EMA")
    if ema_cls:
        ema_indicator_default = ema_cls() # Verwendet Default-Parameter aus Klassendefinition
        logger.info(f"EMA Default Parameter: {ema_indicator_default.current_params}")
        df_ema_default = ema_indicator_default.calculate(df.copy())
        logger.info("Daten mit EMA (Default, letzte 5 Zeilen):")
        logger.info(df_ema_default[['close', ema_indicator_default.output_field_names[0]]].tail())

    logger.info("\n--- Test: Indikator auf Daten ohne 'close'-Spalte (sollte Fehler loggen und NAs erzeugen) ---")
    df_no_close = df[['open', 'high', 'low', 'volume']].copy()
    if sma_cls:
        sma_indicator_err = sma_cls(length=5)
        df_sma_err = sma_indicator_err.calculate(df_no_close)
        logger.info("Daten (ohne Close) mit SMA (sollte NAs enthalten):")
        logger.info(df_sma_err.tail())


    # Teste Discovery (setze voraus, dass die Klassen oben nicht mit @register_indicator dekoriert sind)
    # Um es richtig zu testen, müsste man die explizite Registrierung oben auskommentieren.
    # Hier ist es eher eine Demonstration, dass es aufgerufen werden kann.
    logger.info("\n--- Teste discover_indicators (kann bereits registrierte Indikatoren erneut loggen, wenn nicht schon vorhanden) ---")
    # Temporär einen Indikator entfernen, um zu sehen, ob Discovery ihn findet
    if "SMA" in _INDICATORS_REGISTRY:
        del _INDICATORS_REGISTRY["SMA"]
        logger.debug("SMA temporär aus Registry entfernt für Discovery-Test.")

    initial_registry_keys = set(_INDICATORS_REGISTRY.keys())
    discover_indicators() # Sollte SMA wieder hinzufügen, wenn es nicht explizit registriert wurde
    final_registry_keys = set(_INDICATORS_REGISTRY.keys())

    newly_discovered = final_registry_keys - initial_registry_keys
    if newly_discovered:
        logger.info(f"Durch Discovery neu hinzugefügte Indikatoren: {newly_discovered}")
    else:
        logger.info("Keine neuen Indikatoren durch Discovery hinzugefügt (wahrscheinlich schon alle explizit registriert oder keine neuen Klassen gefunden).")

    if "SMA" in _INDICATORS_REGISTRY:
        logger.info("SMA ist nach Discovery (wieder) in der Registry.")
    else:
        logger.warning("SMA wurde durch Discovery nicht gefunden/registriert (prüfe Implementierung).")


    logger.info("--- Test des Indikatoren-Moduls beendet ---")
