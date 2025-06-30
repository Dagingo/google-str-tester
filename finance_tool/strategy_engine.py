# finance_tool/strategy_engine.py
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from .strategy_definition import StrategyDefinition, Condition, Rule, SignalType, ConditionOperator, LogicOperator
from .indicators import TechnicalIndicator, get_indicator_class # Für Typ-Hinweise und potenziellen dynamischen Abruf

logger = logging.getLogger(__name__)

class StrategyEvaluator:
    """
    Wertet eine definierte Handelsstrategie auf gegebenen Daten (inkl. Indikatoren) aus
    und generiert Handelssignale.
    """
    def __init__(self, strategy_definition: StrategyDefinition,
                 price_data_cols: Dict[str, str] = None):
        """
        Args:
            strategy_definition (StrategyDefinition): Die zu evaluierende Strategiedefinition.
            price_data_cols (Dict[str, str], optional): Mapping für Preisdatenspalten,
                falls sie von Standard ('open', 'high', 'low', 'close', 'volume') abweichen.
                Beispiel: {'close': 'ClosePrice', 'open': 'OpenPrice'}
                Wird verwendet, wenn eine Bedingung den Pseudo-Indikator "Price" verwendet.
        """
        self.strategy_def = strategy_definition
        self.price_data_cols = price_data_cols if price_data_cols else {
            'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'
        }
        logger.info(f"StrategyEvaluator für Strategie '{self.strategy_def.name}' initialisiert.")

    def _get_series(self, data: pd.DataFrame, indicator_name: str, output_field: str,
                    params: Optional[Dict[str, Any]] = None) -> Optional[pd.Series]:
        """
        Holt die benötigte Datenserie (Indikatorwert oder Preis) aus dem DataFrame.
        Indikatoren sollten bereits berechnet und im DataFrame vorhanden sein.
        Diese Methode ist dafür gedacht, die Spalten basierend auf der Condition-Definition zu finden.
        Die eigentliche Indikatorberechnung erfolgt *vor* dem Aufruf von generate_signals.
        """
        if indicator_name.lower() == "price": # Pseudo-Indikator für Preisdaten
            col_name = self.price_data_cols.get(output_field.lower())
            if col_name and col_name in data.columns:
                return data[col_name]
            else:
                logger.warning(f"Preis-Feld '{output_field}' (gemappt zu '{col_name}') nicht in Daten gefunden. Verfügbar: {list(data.columns)}")
                return None
        else:
            # Für echte Indikatoren: Der Spaltenname im DataFrame sollte idealerweise
            # dem output_field entsprechen, wie in TechnicalIndicator.output_field_names definiert.
            # Wenn Indikatoren mit Parametern unterschiedliche Spaltennamen erzeugen (z.B. SMA_20, SMA_50),
            # muss die Datenvorbereitung (data_pipeline) sicherstellen, dass diese Spalten
            # eindeutig benannt und im DataFrame vorhanden sind, oder dass die Condition
            # den genauen Spaltennamen kennt (was weniger flexibel ist).
            # Annahme hier: output_field ist der direkte Spaltenname im DataFrame.
            # Die `params` könnten verwendet werden, um den Spaltennamen dynamisch zu konstruieren,
            # falls die Pipeline dies nicht bereits getan hat (z.B. f"{indicator_name}_{params['length']}_{output_field}").
            # Fürs Erste nehmen wir an, output_field ist der exakte Spaltenname.
            # Beispiel: Ein SMA(20) könnte als Spalte 'sma_20' im DataFrame sein, dann wäre output_field='sma_20'.
            # Oder, wenn die Indikator-Klasse immer 'sma' ausgibt, dann output_field='sma'.
            # Unsere aktuellen Indikatorklassen (SMAIndicator etc.) versuchen, standardisierte Namen (z.B. 'sma') zu verwenden.

            # Konstruiere einen möglichen Spaltennamen, falls Parameter relevant sind
            # Dies ist eine Vereinfachung. Eine robustere Lösung würde die `output_field_names` der Indikator-Klasse
            # und die Parameter berücksichtigen, um den korrekten Spaltennamen abzuleiten.
            # Für jetzt: Wir nehmen an, dass der `output_field` in der Condition dem Spaltennamen im DataFrame entspricht.
            # Wenn params vorhanden sind und der Indikatorname + Parameter einen spezifischen Spaltennamen ergibt,
            # müsste dies hier oder in der Datenaufbereitung berücksichtigt werden.
            # Beispiel: SMA(length=20) -> Spalte 'sma' (wenn so von SMAIndicator.calculate erzeugt)
            # Beispiel: SMA(length=50) -> Spalte 'sma' (wenn nur ein SMA im DF ist, sonst Unterscheidung nötig!)
            # Wenn die Pipeline mehrere Instanzen desselben Indikators mit unterschiedlichen Parametern hinzufügt,
            # müssen die Spaltennamen eindeutig sein, z.B. 'RSI_14_rsi', 'SMA_20_sma', 'SMA_50_sma'.
            # Dann müsste die Condition den output_field entsprechend setzen.

            # Hier nehmen wir an, dass `output_field` bereits der korrekte, eindeutige Spaltenname ist,
            # den die `data_pipeline` erzeugt hat.

            if output_field in data.columns:
                return data[output_field]
            else:
                logger.warning(f"Indikator-Feld '{indicator_name}.{output_field}' nicht in Daten gefunden. Verfügbar: {list(data.columns)}")
                return None


    def _evaluate_condition(self, data: pd.DataFrame, condition: Condition) -> pd.Series:
        """Wertet eine einzelne Bedingung aus und gibt eine boolesche Serie zurück."""
        series1 = self._get_series(data, condition.indicator_name, condition.output_field, condition.params1)

        if series1 is None:
            logger.warning(f"Konnte Serie für {condition.indicator_name}.{condition.output_field} nicht finden. Bedingung wird als False ausgewertet.")
            return pd.Series([False] * len(data), index=data.index)

        # Handle Operatoren, die einen zweiten Wert/Serie benötigen
        if condition.operator in ["<", "<=", "==", ">=", ">", "CrossesAbove", "CrossesBelow"]:
            series2 = None
            value_is_series = False
            if condition.indicator2_name and condition.output_field2:
                series2 = self._get_series(data, condition.indicator2_name, condition.output_field2, condition.params2)
                if series2 is None:
                    logger.warning(f"Konnte Serie für {condition.indicator2_name}.{condition.output_field2} nicht finden. Bedingung wird als False ausgewertet.")
                    return pd.Series([False] * len(data), index=data.index)
                value_is_series = True
            elif isinstance(condition.value, (float, int)):
                # Fester Wert
                pass
            else: # value könnte ein Feldname sein
                if isinstance(condition.value, str) and condition.value in data.columns:
                    series2 = data[condition.value] # z.B. Vergleich mit einer anderen Spalte wie 'open'
                    value_is_series = True
                else:
                    logger.warning(f"Ungültiger Wert '{condition.value}' für Bedingung '{condition}'. Fester Wert oder gültiger Spaltenname erwartet. Bedingung wird als False ausgewertet.")
                    return pd.Series([False] * len(data), index=data.index)

            # Auswertung der Operatoren
            op = condition.operator
            if op == "<": return series1 < (series2 if value_is_series else condition.value)
            if op == "<=": return series1 <= (series2 if value_is_series else condition.value)
            if op == "==": return series1 == (series2 if value_is_series else condition.value) # Vorsicht mit Float-Vergleichen
            if op == ">=": return series1 >= (series2 if value_is_series else condition.value)
            if op == ">": return series1 > (series2 if value_is_series else condition.value)

            # Kreuzungsoperatoren
            # series1.shift(1) ist der Wert von series1 in der Vorperiode
            # series2_val ist entweder series2 oder der feste Wert condition.value
            s2_val = series2 if value_is_series else condition.value
            if op == "CrossesAbove":
                return (series1.shift(1) < s2_val.shift(1) if value_is_series else series1.shift(1) < s2_val) & \
                       (series1 > s2_val)
            if op == "CrossesBelow":
                return (series1.shift(1) > s2_val.shift(1) if value_is_series else series1.shift(1) > s2_val) & \
                       (series1 < s2_val)

        # Handle unäre Operatoren
        elif condition.operator == "IsRising":
            return series1 > series1.shift(1)
        elif condition.operator == "IsFalling":
            return series1 < series1.shift(1)

        logger.warning(f"Unbekannter oder nicht unterstützter Operator '{condition.operator}' in Bedingung. Wird als False ausgewertet.")
        return pd.Series([False] * len(data), index=data.index)


    def _evaluate_rule(self, data: pd.DataFrame, rule: Rule) -> pd.Series:
        """Wertet eine einzelne Regel aus und gibt eine boolesche Serie zurück, die angibt, wann die Regel zutrifft."""
        if not rule.conditions:
            return pd.Series([False] * len(data), index=data.index)

        # Werte alle Bedingungen der Regel aus
        condition_results = [self._evaluate_condition(data, cond) for cond in rule.conditions]

        # Kombiniere die Ergebnisse der Bedingungen basierend auf dem logischen Operator
        if rule.logic_operator == "AND":
            # Starte mit True für alle Zeilen, dann UND-verknüpfe mit jeder Bedingung
            final_result = pd.Series([True] * len(data), index=data.index)
            for res_series in condition_results:
                final_result = final_result & res_series
        elif rule.logic_operator == "OR":
            # Starte mit False für alle Zeilen, dann ODER-verknüpfe
            final_result = pd.Series([False] * len(data), index=data.index)
            for res_series in condition_results:
                final_result = final_result | res_series
        else:
            logger.error(f"Unbekannter logischer Operator '{rule.logic_operator}' in Regel. Wird als False ausgewertet.")
            return pd.Series([False] * len(data), index=data.index)

        return final_result

    def generate_signals(self, data_with_indicators: pd.DataFrame) -> pd.Series:
        """
        Generiert Handelssignale basierend auf der Strategiedefinition.
        Signale: 1 für KAUFEN, -1 für VERKAUFEN, 0 für HALTEN/NEUTRAL.
        """
        logger.info(f"Generiere Signale für Strategie '{self.strategy_def.name}' mit {len(data_with_indicators)} Datenpunkten.")
        if data_with_indicators.empty:
            logger.warning("generate_signals: Leerer DataFrame übergeben. Gebe leere Signal-Serie zurück.")
            return pd.Series(dtype=np.int8)

        # Initialisiere Signal-Serie mit 0 (Neutral/Halten)
        signals = pd.Series(0, index=data_with_indicators.index, dtype=np.int8)

        # Werte Kaufregeln aus
        # Wenn mehrere Kaufregeln zutreffen, wird das erste Signal genommen (einfache Logik)
        # Eine komplexere Logik könnte Signale gewichten oder kombinieren.
        final_buy_signal = pd.Series(False, index=data_with_indicators.index)
        for rule in self.strategy_def.buy_rules:
            if rule.signal == "BUY": # Sicherstellen, dass es eine Kaufregel ist
                rule_triggers = self._evaluate_rule(data_with_indicators, rule)
                final_buy_signal = final_buy_signal | rule_triggers
            else:
                logger.warning(f"Regel '{rule.description}' in 'buy_rules' hat unerwarteten Signaltyp '{rule.signal}'. Wird ignoriert.")

        signals.loc[final_buy_signal] = 1

        # Werte Verkaufsregeln aus
        final_sell_signal = pd.Series(False, index=data_with_indicators.index)
        for rule in self.strategy_def.sell_rules:
            if rule.signal == "SELL":
                rule_triggers = self._evaluate_rule(data_with_indicators, rule)
                final_sell_signal = final_sell_signal | rule_triggers
            else:
                logger.warning(f"Regel '{rule.description}' in 'sell_rules' hat unerwarteten Signaltyp '{rule.signal}'. Wird ignoriert.")

        # Verkaufsignale überschreiben Kaufsignale, wenn beide am selben Tag auftreten (übliche Priorität)
        signals.loc[final_sell_signal] = -1

        # Optional: Werte Halteregeln aus (könnte verwendet werden, um explizit eine neutrale Position zu erzwingen)
        if self.strategy_def.hold_rules:
            final_hold_signal = pd.Series(False, index=data_with_indicators.index)
            for rule in self.strategy_def.hold_rules:
                if rule.signal == "HOLD":
                     rule_triggers = self._evaluate_rule(data_with_indicators, rule)
                     final_hold_signal = final_hold_signal | rule_triggers
                else:
                    logger.warning(f"Regel '{rule.description}' in 'hold_rules' hat unerwarteten Signaltyp '{rule.signal}'. Wird ignoriert.")
            signals.loc[final_hold_signal & (signals == 0)] = 0 # Setze auf 0, wenn Hold-Regel zutrifft UND noch kein Kauf/Verkaufssignal

        # Fülle NaNs, die durch shift() entstehen könnten, am Anfang mit 0
        signals.fillna(0, inplace=True)

        logger.info(f"Signalerzeugung abgeschlossen. Signalverteilung: \n{signals.value_counts(normalize=True).mul(100).round(2).astype(str) + '%'}")
        return signals.astype(np.int8)


if __name__ == "__main__":
    # Logging-Setup für den Testlauf
    if not logging.getLogger().hasHandlers():
        import sys
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    from .indicators import SMAIndicator, RSIIndicator # Importiere Indikatoren für den Test

    logger.info("--- Test der StrategyEngine ---")

    # 1. Beispieldaten erstellen (Preisdaten + bereits berechnete Indikatorwerte)
    num_points = 100
    prices = [10 + i * 0.1 + np.sin(i / 5) for i in range(num_points)] # Preisreihe mit Trend und Sinus
    data = pd.DataFrame({'close': prices, 'open': prices, 'high': prices, 'low': prices}) # Vereinfacht
    data.index = pd.to_datetime(pd.date_range(start='2023-01-01', periods=len(data)))

    # Berechne Indikatoren und füge sie zum DataFrame hinzu
    # Annahme: Die Spaltennamen entsprechen den output_fields der Indikatoren
    sma20 = SMAIndicator(length=20)
    data_with_inds = sma20.calculate(data.copy()) # Erzeugt Spalte 'sma' (für SMA_20)
    data_with_inds.rename(columns={'sma': 'sma_20'}, inplace=True) # Umbenennen für Klarheit im Test

    sma50 = SMAIndicator(length=50)
    data_with_inds = sma50.calculate(data_with_inds) # Erzeugt Spalte 'sma' (für SMA_50)
    data_with_inds.rename(columns={'sma': 'sma_50'}, inplace=True)

    rsi14 = RSIIndicator(length=14)
    data_with_inds = rsi14.calculate(data_with_inds) # Erzeugt Spalte 'rsi' (für RSI_14)

    logger.debug("DataFrame mit Indikatoren (erste paar Zeilen):")
    logger.debug(data_with_inds.head().to_string())
    logger.debug("DataFrame mit Indikatoren (letzte paar Zeilen relevante Spalten):")
    logger.debug(data_with_inds[['close', 'sma_20', 'sma_50', 'rsi']].tail().to_string())


    # 2. Beispiel-Strategiedefinition erstellen
    # Kaufbedingung 1: RSI < 30
    cond_buy_rsi = Condition("RSI", "rsi", "<", 30, params1={"length": 14}) # Annahme: 'rsi' ist die Spalte für RSI(14)
    # Kaufbedingung 2: SMA20 kreuzt über SMA50
    cond_buy_sma_cross = Condition("SMA", "sma_20", "CrossesAbove", None,
                                   indicator2_name="SMA", output_field2="sma_50",
                                   params1={"length": 20}, params2={"length": 50})

    buy_rule = Rule(conditions=[cond_buy_rsi, cond_buy_sma_cross], logic_operator="OR", signal="BUY", description="RSI oversold OR SMA Crossover")

    # Verkaufsbedingung 1: RSI > 70
    cond_sell_rsi = Condition("RSI", "rsi", ">", 70, params1={"length": 14})
    # Verkaufsbedingung 2: Preis (Close) kreuzt unter SMA20
    cond_sell_price_cross_sma = Condition("Price", "close", "CrossesBelow", None,
                                          indicator2_name="SMA", output_field2="sma_20",
                                          params2={"length": 20})

    sell_rule = Rule(conditions=[cond_sell_rsi, cond_sell_price_cross_sma], logic_operator="AND", signal="SELL", description="RSI overbought AND Price crosses SMA20")

    strategy_def = StrategyDefinition(
        name="Test_RSI_SMA_Strategy",
        description="Teststrategie mit RSI und SMA Crossover.",
        buy_rules=[buy_rule],
        sell_rules=[sell_rule]
    )
    logger.info(f"Test-Strategie definiert: {strategy_def}")

    # 3. StrategyEvaluator instanziieren
    evaluator = StrategyEvaluator(strategy_def, price_data_cols={'close': 'close'}) # Standard 'close' Spalte

    # 4. Signale generieren
    logger.info("Generiere Signale...")
    generated_signals = evaluator.generate_signals(data_with_inds.copy()) # Korrigierter Variablenname

    logger.info("\nGenerierte Signale (erste 20 und letzte 20):")
    logger.info(generated_signals.head(20).to_string())
    logger.info("...")
    logger.info(generated_signals.tail(20).to_string())

    signal_counts = generated_signals.value_counts()
    logger.info(f"\nAnzahl der Signale: \n{signal_counts}")

    # Erwarte einige Signale, aber nicht zu viele, und nicht nur Nullen
    if len(signal_counts) > 1 and signal_counts.get(0, 0) < len(generated_signals):
        logger.info("SUCCESS: Signalerzeugung scheint funktioniert zu haben (diverse Signale vorhanden).")
    elif len(signal_counts) == 1 and 0 in signal_counts:
        logger.warning("WARNUNG: Nur neutrale Signale (0) generiert. Überprüfe Daten und Strategielogik.")
    else:
        logger.error("FEHLER: Unerwartetes Ergebnis bei der Signalerzeugung.")

    logger.info("\n--- Test der StrategyEngine beendet ---")
