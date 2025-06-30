# finance_tool/data_pipeline.py
import pandas as pd
import logging
from typing import Dict, Any, Set, Tuple, Optional

from .strategy_definition import StrategyDefinition, Condition
from .indicators import get_indicator_class
from .data_fetcher import fetch_data

logger = logging.getLogger(__name__)

def get_unique_indicator_configs_from_strategy(strategy_def: StrategyDefinition) -> Set[Tuple[str, Tuple[Tuple[str, Any], ...], str]]:
    """
    Sammelt alle einzigartigen Indikatorkonfigurationen (Name, sortierte Parameter, Output-Feld des Indikators selbst),
    die in einer Strategiedefinition benötigt werden.
    Gibt ein Set von Tupeln zurück: (indicator_name, frozenset_of_params_items, indicator_native_output_field)
    """
    required_configs = set()

    rules = strategy_def.buy_rules + strategy_def.sell_rules + strategy_def.hold_rules
    for rule in rules:
        for cond in rule.conditions:
            # Indikator 1
            if cond.indicator_name.lower() != "price": # Preisdaten nicht als Indikator hier behandeln
                # Sortiere Parameter für konsistente Schlüssel
                # Das output_field in der Condition ist der *eindeutige Spaltenname im DataFrame*.
                # Wir müssen hier aber auf das *native* Output-Feld des Indikators zugreifen,
                # um zu wissen, welche Spalte der Indikator selbst erzeugt.
                # Diese Funktion ist dafür da, die *Berechnungs*konfigurationen zu sammeln.
                # Der `cond.output_field` wird später verwendet, um die richtige Spalte auszuwählen.
                # Hier müssen wir wissen, welche nativen Felder der Indikator erzeugt.

                indicator_cls = get_indicator_class(cond.indicator_name)
                if not indicator_cls:
                    logger.warning(f"Sammle Indikatorkonfigs: Indikatorklasse für '{cond.indicator_name}' nicht gefunden. Überspringe.")
                    continue

                # Annahme: Die Strategie-Engine wird später auf *eines* dieser nativen Felder zugreifen.
                # Die `Condition` muss spezifizieren, welches native Feld gemeint ist, wenn ein Indikator mehrere hat (z.B. MACD).
                # Der `output_field` in der Condition sollte idealerweise diesen nativen Feldnamen enthalten
                # oder die Pipeline muss ihn ableiten können.
                # Für diesen Schritt nehmen wir an, dass cond.output_field (nach Entfernung von Präfix/Suffix)
                # einem der nativen output_field_names des Indikators entspricht.

                # Beispiel: Condition.output_field = "SMA_length20_sma"
                # Wir extrahieren daraus den nativen Teil "sma".
                # Dies ist etwas heikel. Besser wäre, wenn Condition den nativen Feldnamen separat speichert.
                # Für jetzt: Wir nehmen an, dass das letzte Segment nach dem letzten '_' das native Feld ist,
                # oder dass `indicator_cls.output_field_names[0]` verwendet wird, wenn es nur eines gibt.

                native_output_field_to_match = cond.output_field # Dies ist der *Zielspaltenname* im DataFrame
                # Versuche, den nativen Feldnamen zu erraten, wenn der output_field zusammengesetzt ist.
                # Dies ist eine Vereinfachung und könnte verbessert werden.
                guessed_native_field = native_output_field_to_match
                if indicator_cls.output_field_names:
                    found_native = False
                    for native_field in indicator_cls.output_field_names:
                        if native_field in native_output_field_to_match: # z.B. 'sma' in 'SMA_length20_sma'
                            guessed_native_field = native_field
                            found_native = True
                            break
                    if not found_native:
                         # Fallback auf das erste native Feld, wenn keine Übereinstimmung
                        guessed_native_field = indicator_cls.output_field_names[0]
                        logger.debug(f"Kein passendes natives Feld für '{native_output_field_to_match}' in '{cond.indicator_name}' gefunden. Verwende Fallback: '{guessed_native_field}'.")

                params_tuple = tuple(sorted(cond.params1.items()))
                required_configs.add((cond.indicator_name, params_tuple, guessed_native_field))


            # Indikator 2 (falls vorhanden)
            if cond.indicator2_name and cond.indicator2_name.lower() != "price":
                indicator2_cls = get_indicator_class(cond.indicator2_name)
                if not indicator2_cls:
                    logger.warning(f"Sammle Indikatorkonfigs: Indikatorklasse für '{cond.indicator2_name}' nicht gefunden. Überspringe.")
                    continue

                native_output_field2_to_match = cond.output_field2
                guessed_native_field2 = native_output_field2_to_match
                if indicator2_cls.output_field_names:
                    found_native2 = False
                    for native_field in indicator2_cls.output_field_names:
                        if native_field in native_output_field2_to_match:
                            guessed_native_field2 = native_field
                            found_native2 = True
                            break
                    if not found_native2:
                        guessed_native_field2 = indicator2_cls.output_field_names[0]
                        logger.debug(f"Kein passendes natives Feld für '{native_output_field2_to_match}' in '{cond.indicator2_name}' gefunden. Verwende Fallback: '{guessed_native_field2}'.")

                params2_tuple = tuple(sorted(cond.params2.items()))
                required_configs.add((cond.indicator2_name, params2_tuple, guessed_native_field2))

    logger.debug(f"Einzigartige Indikatorkonfigurationen aus Strategie extrahiert: {required_configs}")
    return required_configs

def generate_unique_column_name(indicator_name: str, params: Dict[str, Any], native_output_field: str) -> str:
    """
    Generiert einen eindeutigen Spaltennamen für einen Indikator mit spezifischen Parametern und seinem nativen Output-Feld.
    Beispiel: SMA, {'length': 20}, 'sma' -> 'SMA_length20_sma'
               MACD, {'fast':12,...}, 'macd_line' -> 'MACD_fast12_slow26_signal9_macd_line'
    """
    if not params: # Keine Parameter
        return f"{indicator_name}_{native_output_field}"

    param_str = "_".join(f"{k}{v}" for k, v in sorted(params.items()))
    return f"{indicator_name}_{param_str}_{native_output_field}"


def prepare_data_for_strategy(
    ticker: str,
    start_date: str,
    end_date: str,
    interval: str,
    strategy_def: StrategyDefinition,
    # price_data_cols_map: Optional[Dict[str, str]] = None # Vorerst nicht verwendet, da fetch_data Standardnamen liefert
) -> Optional[pd.DataFrame]:
    """
    Bereitet Daten für eine gegebene Strategie vor:
    1. Ruft Roh-Preisdaten ab.
    2. Identifiziert alle benötigten Indikatoren und deren Parameter aus der Strategiedefinition.
    3. Berechnet diese Indikatoren und fügt sie dem DataFrame hinzu.
       Stellt sicher, dass jede Indikatorinstanz (mit ihren Parametern) eine eindeutig benannte Spalte erhält.
       Die `output_field` Namen in den Conditions der StrategyDefinition *müssen* diese eindeutigen Namen verwenden.
    """
    logger.info(f"prepare_data_for_strategy: Starte Datenvorbereitung für Ticker '{ticker}', Strategie '{strategy_def.name}'.")

    # 1. Rohdaten abrufen
    raw_data = fetch_data(ticker_symbol=ticker, start_date=start_date, end_date=end_date, interval=interval)
    if raw_data is None or raw_data.empty:
        logger.error(f"Konnte keine Rohdaten für Ticker '{ticker}' abrufen.")
        return None

    # Stelle sicher, dass die Standardspaltennamen vorhanden sind (OHLCV)
    # pandas_ta benötigt oft 'open', 'high', 'low', 'close', 'volume' in Kleinbuchstaben.
    # yfinance liefert sie typischerweise als 'Open', 'High', 'Low', 'Close', 'Volume'.
    # Wir normalisieren sie hier.
    rename_map = {
        'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
    }
    # Nur Spalten umbenennen, die existieren
    cols_to_rename = {k: v for k, v in rename_map.items() if k in raw_data.columns}
    if cols_to_rename:
        raw_data.rename(columns=cols_to_rename, inplace=True)
        logger.debug(f"Spalten umbenannt zu Kleinbuchstaben: {cols_to_rename}")


    data_with_indicators = raw_data.copy()

    # 2. Einzigartige Indikatorkonfigurationen sammeln
    # Dies muss die *nativen* Output-Felder der Indikatoren sammeln, nicht die zusammengesetzten Spaltennamen.
    # Die Logik in get_unique_indicator_configs_from_strategy wurde angepasst.

    # Wir müssen die *tatsächlich benötigten* Indikatoren basierend auf den `indicator_name`
    # und `params` in den Conditions sammeln.
    # Die `output_field` in der Condition ist der *Zielname* im DataFrame.

    unique_calculations_needed = set() # Set von (indicator_name, frozenset_params_tuple)
    rules = strategy_def.buy_rules + strategy_def.sell_rules + strategy_def.hold_rules
    for rule in rules:
        for cond in rule.conditions:
            if cond.indicator_name.lower() != "price":
                params_tuple = tuple(sorted(cond.params1.items()))
                unique_calculations_needed.add((cond.indicator_name, params_tuple))
            if cond.indicator2_name and cond.indicator2_name.lower() != "price":
                params2_tuple = tuple(sorted(cond.params2.items()))
                unique_calculations_needed.add((cond.indicator2_name, params2_tuple))

    logger.debug(f"Benötigte einzigartige Indikatorberechnungen: {unique_calculations_needed}")

    # 3. Indikatoren berechnen und hinzufügen
    for indicator_name, params_tuple in unique_calculations_needed:
        params_dict = dict(params_tuple)
        indicator_cls = get_indicator_class(indicator_name)

        if not indicator_cls:
            logger.warning(f"Indikatorklasse für '{indicator_name}' nicht gefunden. Kann nicht berechnet werden.")
            continue

        try:
            indicator_instance = indicator_cls(**params_dict)
            logger.debug(f"Berechne Indikator: {indicator_name} mit Parametern {params_dict}")

            # Temporärer DataFrame für die Berechnung dieses einen Indikators, um Spaltenkollisionen zu vermeiden,
            # falls die 'calculate'-Methode des Indikators die Spalten immer gleich benennt (z.B. immer 'sma').
            temp_df_for_calc = data_with_indicators.copy() # Nur Preisdaten reichen oft
            indicator_df_results = indicator_instance.calculate(temp_df_for_calc) # Gibt DF mit Indikatorspalten zurück

            # Füge die berechneten Spalten zum Haupt-DataFrame hinzu, mit eindeutigen Namen
            for native_field in indicator_cls.output_field_names:
                if native_field in indicator_df_results.columns: # Sicherstellen, dass der Indikator das Feld erzeugt hat
                    unique_col_name = generate_unique_column_name(indicator_name, params_dict, native_field)
                    if unique_col_name in data_with_indicators.columns:
                        logger.warning(f"Spalte '{unique_col_name}' existiert bereits und wird überschrieben. Dies sollte nicht passieren bei korrekter Logik.")
                    data_with_indicators[unique_col_name] = indicator_df_results[native_field]
                    logger.debug(f"Indikatorspalte '{native_field}' von {indicator_name}({params_dict}) als '{unique_col_name}' zum DataFrame hinzugefügt.")
                else:
                    logger.warning(f"Natives Feld '{native_field}' nicht im Ergebnis von {indicator_name}({params_dict}) gefunden. Spalten: {list(indicator_df_results.columns)}")

        except Exception as e:
            logger.error(f"Fehler bei der Berechnung oder Integration von Indikator '{indicator_name}' mit Parametern {params_dict}: {e}", exc_info=True)
            # Optional: Fehlende Spalten mit NaN füllen, damit die Strategie-Engine nicht abbricht
            # for native_field in indicator_cls.output_field_names:
            #     unique_col_name = generate_unique_column_name(indicator_name, params_dict, native_field)
            #     data_with_indicators[unique_col_name] = pd.NA


    logger.info(f"Datenvorbereitung für Strategie '{strategy_def.name}' abgeschlossen. DataFrame Spalten: {list(data_with_indicators.columns)}")
    return data_with_indicators


if __name__ == "__main__":
    if not logging.getLogger().hasHandlers():
        import sys
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    from .strategy_definition import Condition, Rule, StrategyDefinition # Für Test

    logger.info("--- Test der DataPipeline ---")

    # Beispiel-Strategiedefinition (angepasst, um eindeutige Spaltennamen zu verwenden)
    # Die `output_field`s müssen jetzt die von `generate_unique_column_name` erzeugten Namen sein.

    # Bedingung 1: RSI(14) < 30
    # Nativer Output von RSIIndicator ist 'rsi'. Eindeutiger Name: 'RSI_length14_rsi'
    cond_buy_rsi = Condition(
        indicator_name="RSI", output_field="RSI_length14_rsi", params1={"length": 14},
        operator="<", value=30
    )

    # Bedingung 2: SMA(20) > SMA(50)
    # Eindeutige Namen: 'SMA_length20_sma' und 'SMA_length50_sma'
    cond_buy_sma_cross = Condition(
        indicator_name="SMA", output_field="SMA_length20_sma", params1={"length": 20},
        operator=">", value=None, # value wird für Indikator-Indikator-Vergleich verwendet
        indicator2_name="SMA", output_field2="SMA_length50_sma", params2={"length": 50}
    )

    buy_rule = Rule(conditions=[cond_buy_rsi, cond_buy_sma_cross], logic_operator="OR", signal="BUY")

    # Verkaufsbedingung: Preis (Close) kreuzt unter SMA(20)
    # 'Price' ist speziell. 'close' ist der native Feldname.
    # 'SMA_length20_sma' ist der eindeutige Name für den SMA(20).
    cond_sell_price_cross = Condition(
        indicator_name="Price", output_field="close", # StrategyEngine wird 'close' aus Rohdaten nehmen
        operator="CrossesBelow", value=None,
        indicator2_name="SMA", output_field2="SMA_length20_sma", params2={"length": 20}
    )
    sell_rule = Rule(conditions=[cond_sell_price_cross], logic_operator="AND", signal="SELL")

    test_strategy = StrategyDefinition(
        name="PipelineTestStrategy",
        description="Teststrategie für DataPipeline",
        buy_rules=[buy_rule],
        sell_rules=[sell_rule]
    )

    logger.info(f"Test-Strategie für Pipeline: {test_strategy}")
    for rule in test_strategy.buy_rules + test_strategy.sell_rules:
        for cond in rule.conditions:
            logger.debug(f"  Condition in Test Strat: {cond}")


    # Teste prepare_data_for_strategy
    # Verwende einen echten Ticker, um Datenabruf zu testen
    ticker_symbol = "AAPL"
    # Kurzer Zeitraum für schnellen Test, aber lang genug für Indikatoren
    start_dt = (pd.Timestamp.now() - pd.Timedelta(days=300)).strftime('%Y-%m-%d')
    end_dt = pd.Timestamp.now().strftime('%Y-%m-%d')

    logger.info(f"Rufe prepare_data_for_strategy für {ticker_symbol} von {start_dt} bis {end_dt} auf.")

    prepared_df = prepare_data_for_strategy(
        ticker=ticker_symbol,
        start_date=start_dt,
        end_date=end_dt,
        interval="1d",
        strategy_def=test_strategy
    )

    if prepared_df is not None and not prepared_df.empty:
        logger.info(f"prepare_data_for_strategy erfolgreich. {len(prepared_df)} Zeilen.")
        logger.info("DataFrame Spalten:")
        for col in prepared_df.columns:
            logger.info(f"  - {col}")

        logger.info("Letzte 5 Zeilen des vorbereiteten DataFrames (ausgewählte Spalten):")
        cols_to_show = ['close', 'RSI_length14_rsi', 'SMA_length20_sma', 'SMA_length50_sma']
        # Nur Spalten anzeigen, die auch wirklich existieren
        cols_to_show = [col for col in cols_to_show if col in prepared_df.columns]
        if cols_to_show:
            logger.info(prepared_df[cols_to_show].tail().to_string())
        else:
            logger.warning("Keine der erwarteten Indikatorspalten im DataFrame gefunden zum Anzeigen.")

        # Überprüfe, ob die erwarteten Spalten vorhanden sind
        expected_cols = ["close", "RSI_length14_rsi", "SMA_length20_sma", "SMA_length50_sma"]
        missing_cols = [col for col in expected_cols if col not in prepared_df.columns]
        if not missing_cols:
            logger.info("Alle erwarteten Indikatorspalten sind im DataFrame vorhanden.")
        else:
            logger.error(f"Fehlende erwartete Spalten im DataFrame: {missing_cols}")
    else:
        logger.error("prepare_data_for_strategy hat keinen DataFrame oder einen leeren DataFrame zurückgegeben.")

    logger.info("--- Test der DataPipeline beendet ---")
