# finance_tool/strategy_definition.py
import json
import logging
from typing import List, Dict, Any, Literal, Optional, Union

logger = logging.getLogger(__name__)

# Typdefinitionen für Klarheit
SignalType = Literal["BUY", "SELL", "HOLD", "NONE"] # NONE für keine Aktion
LogicOperator = Literal["AND", "OR"]
ConditionOperator = Literal[
    "<", "<=", "==", ">=", ">",
    "CrossesAbove", "CrossesBelow",
    "IsRising", "IsFalling" # Einfache Trendbedingungen
]

class Condition:
    """
    Repräsentiert eine einzelne Bedingung innerhalb einer Handelsregel.
    Eine Bedingung vergleicht typischerweise einen Indikatorwert mit einem Schwellenwert
    oder zwei Indikatorwerte miteinander.
    """
    def __init__(self, indicator_name: str, output_field: str, operator: ConditionOperator,
                 value: Union[float, int, str], # Wert kann Zahl sein oder Name eines anderen Indikatorfeldes
                 indicator2_name: Optional[str] = None, # Für Vergleiche zwischen zwei Indikatoren
                 output_field2: Optional[str] = None,
                 params1: Optional[Dict[str, Any]] = None, # Parameter für Indikator 1
                 params2: Optional[Dict[str, Any]] = None  # Parameter für Indikator 2
                ):
        self.indicator_name = indicator_name
        self.output_field = output_field # Welches Feld des Indikators (z.B. 'sma', 'rsi', 'macd_line')
        self.operator = operator
        self.value = value # Kann ein fester Wert oder der Schlüssel für einen anderen Indikator sein
        self.indicator2_name = indicator2_name
        self.output_field2 = output_field2
        self.params1 = params1 if params1 is not None else {}
        self.params2 = params2 if params2 is not None else {}

        # Validierung (einfach)
        if self.operator in ["CrossesAbove", "CrossesBelow", "IsRising", "IsFalling"]:
            if self.operator in ["CrossesAbove", "CrossesBelow"] and not (self.indicator2_name and self.output_field2):
                 # Bei CrossesAbove/Below kann 'value' auch ein fester Wert sein, aber typischerweise ist es ein anderer Indikator
                 pass # Akzeptiere auch value als festen Wert für Kreuzungen (z.B. Preis kreuzt MA)
            elif self.operator in ["IsRising", "IsFalling"] and (self.indicator2_name or self.output_field2 or self.value is not None):
                 # IsRising/IsFalling benötigen keine value oder zweiten Indikator
                 if self.value is not None: # value sollte None sein für IsRising/Falling
                    logger.warning(f"Condition: For '{self.operator}', 'value' should ideally be None. Value '{self.value}' will be ignored.")
                    self.value = None # Setze es auf None, da es nicht verwendet wird
        elif not self.indicator2_name and isinstance(self.value, str):
            logger.warning(f"Condition: 'value' is a string ('{self.value}') but 'indicator2_name' is not set. "
                           f"This string will be treated as a literal if not handled as an indicator key by the engine.")


    def to_dict(self) -> Dict[str, Any]:
        return {
            "indicator_name": self.indicator_name, "output_field": self.output_field,
            "operator": self.operator, "value": self.value,
            "indicator2_name": self.indicator2_name, "output_field2": self.output_field2,
            "params1": self.params1, "params2": self.params2
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Condition":
        return cls(
            indicator_name=data["indicator_name"], output_field=data["output_field"],
            operator=data["operator"], value=data["value"],
            indicator2_name=data.get("indicator2_name"), output_field2=data.get("output_field2"),
            params1=data.get("params1", {}), params2=data.get("params2", {})
        )

    def __repr__(self):
        if self.indicator2_name:
            return (f"Condition({self.indicator_name}({self.params1}).{self.output_field} {self.operator} "
                    f"{self.indicator2_name}({self.params2}).{self.output_field2})")
        elif self.operator in ["IsRising", "IsFalling"]:
            return f"Condition({self.indicator_name}({self.params1}).{self.output_field} {self.operator})"
        else:
            return f"Condition({self.indicator_name}({self.params1}).{self.output_field} {self.operator} {self.value})"


class Rule:
    """
    Repräsentiert eine Handelsregel, bestehend aus einer Liste von Bedingungen
    und einem resultierenden Signal.
    """
    def __init__(self, conditions: List[Condition], logic_operator: LogicOperator, signal: SignalType, description: str = ""):
        if not conditions:
            raise ValueError("Eine Regel muss mindestens eine Bedingung enthalten.")
        self.conditions = conditions
        self.logic_operator = logic_operator # AND oder OR
        self.signal = signal # BUY, SELL, HOLD
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conditions": [c.to_dict() for c in self.conditions],
            "logic_operator": self.logic_operator,
            "signal": self.signal,
            "description": self.description
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rule":
        conditions = [Condition.from_dict(c_data) for c_data in data["conditions"]]
        return cls(conditions, data["logic_operator"], data["signal"], data.get("description", ""))

    def __repr__(self):
        cond_str = f" {self.logic_operator} ".join(map(str, self.conditions))
        return f"Rule([{cond_str}] => {self.signal}, Desc: '{self.description}')"


class StrategyDefinition:
    """
    Definiert eine vollständige Handelsstrategie.
    """
    def __init__(self, name: str, description: str,
                 buy_rules: List[Rule], sell_rules: List[Rule],
                 hold_rules: Optional[List[Rule]] = None, # Optional
                 version: str = "1.0"):
        self.name = name
        self.description = description
        self.buy_rules = buy_rules
        self.sell_rules = sell_rules
        self.hold_rules = hold_rules if hold_rules is not None else []
        self.version = version

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name, "description": self.description, "version": self.version,
            "buy_rules": [r.to_dict() for r in self.buy_rules],
            "sell_rules": [r.to_dict() for r in self.sell_rules],
            "hold_rules": [r.to_dict() for r in self.hold_rules]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyDefinition":
        buy_rules = [Rule.from_dict(r_data) for r_data in data.get("buy_rules", [])]
        sell_rules = [Rule.from_dict(r_data) for r_data in data.get("sell_rules", [])]
        hold_rules = [Rule.from_dict(r_data) for r_data in data.get("hold_rules", [])]
        return cls(data["name"], data["description"], buy_rules, sell_rules, hold_rules, data.get("version", "1.0"))

    def __repr__(self):
        return (f"StrategyDefinition(Name: '{self.name}', Version: {self.version}, "
                f"Buy Rules: {len(self.buy_rules)}, Sell Rules: {len(self.sell_rules)}, Hold Rules: {len(self.hold_rules)})")


def save_strategy_to_json(strategy_def: StrategyDefinition, filepath: str):
    """Speichert eine StrategyDefinition als JSON-Datei."""
    logger.info(f"Speichere Strategie '{strategy_def.name}' nach '{filepath}'.")
    try:
        with open(filepath, 'w') as f:
            json.dump(strategy_def.to_dict(), f, indent=4)
        logger.info(f"Strategie '{strategy_def.name}' erfolgreich gespeichert.")
    except IOError as e:
        logger.error(f"Fehler beim Speichern der Strategie nach '{filepath}': {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Speichern der Strategie: {e}", exc_info=True)
        raise


def load_strategy_from_json(filepath: str) -> Optional[StrategyDefinition]:
    """Lädt eine StrategyDefinition aus einer JSON-Datei."""
    logger.info(f"Lade Strategie von '{filepath}'.")
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        strategy_def = StrategyDefinition.from_dict(data)
        logger.info(f"Strategie '{strategy_def.name}' erfolgreich geladen.")
        return strategy_def
    except FileNotFoundError:
        logger.error(f"Strategie-Datei '{filepath}' nicht gefunden.")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Fehler beim Parsen der JSON-Strategie-Datei '{filepath}': {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unerwarteter Fehler beim Laden der Strategie von '{filepath}': {e}", exc_info=True)
        return None


if __name__ == "__main__":
    # Logging-Setup für den Testlauf
    if not logging.getLogger().hasHandlers():
        import sys
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                            handlers=[logging.StreamHandler(sys.stdout)])

    logger.info("--- Test des StrategyDefinition-Moduls ---")

    # Beispielhafte Bedingungen erstellen
    # Bedingung 1: RSI(14) < 30
    cond_rsi_lt_30 = Condition(
        indicator_name="RSI", output_field="rsi", params1={"length": 14},
        operator="<", value=30
    )
    logger.debug(f"Erstellte Bedingung 1: {cond_rsi_lt_30}")

    # Bedingung 2: SMA(20) > SMA(50) (Kreuzung als Operator wäre besser, hier als einfacher Vergleich)
    cond_sma_gt_sma = Condition(
        indicator_name="SMA", output_field="sma", params1={"length": 20},
        operator=">",
        indicator2_name="SMA", output_field2="sma", params2={"length": 50},
        value=None # value wird ignoriert, wenn indicator2_name gesetzt ist (implizit)
    )
    logger.debug(f"Erstellte Bedingung 2: {cond_sma_gt_sma}")

    # Bedingung 3: Preis (Close) kreuzt über SMA(20)
    # Hier ist 'Close' kein expliziter Indikator, sondern ein Feld aus den Rohdaten.
    # Die StrategyEngine muss dies speziell behandeln.
    # Wir definieren 'Close' als Pseudo-Indikator oder die Engine muss das Feld direkt nutzen können.
    # Für dieses Beispiel verwenden wir einen Pseudo-Indikator "Price" mit Feld "close".
    cond_close_cross_sma20 = Condition(
        indicator_name="Price", output_field="close", # Pseudo-Indikator für Preisdaten
        operator="CrossesAbove",
        indicator2_name="SMA", output_field2="sma", params2={"length": 20},
        value=None
    )
    logger.debug(f"Erstellte Bedingung 3: {cond_close_cross_sma20}")

    # Bedingung 4: MACD-Linie ist steigend
    cond_macd_rising = Condition(
        indicator_name="MACD", output_field="macd_line", params1={"fast":12, "slow":26, "signal":9},
        operator="IsRising", value=None
    )
    logger.debug(f"Erstellte Bedingung 4: {cond_macd_rising}")


    # Beispielhafte Regeln erstellen
    buy_rule1 = Rule(
        conditions=[cond_rsi_lt_30, cond_close_cross_sma20],
        logic_operator="AND",
        signal="BUY",
        description="RSI oversold and price crosses above SMA20"
    )
    logger.debug(f"Erstellte Kaufregel 1: {buy_rule1}")

    sell_rule1 = Rule(
        conditions=[
            Condition(indicator_name="RSI", output_field="rsi", params1={"length": 14}, operator=">", value=70),
            Condition(indicator_name="Price", output_field="close", operator="CrossesBelow", value=None, # value hinzugefügt
                      indicator2_name="SMA", output_field2="sma", params2={"length": 50})
        ],
        logic_operator="OR",
        signal="SELL",
        description="RSI overbought OR price crosses below SMA50"
    )
    logger.debug(f"Erstellte Verkaufsregel 1: {sell_rule1}")

    # Beispielhafte Strategie-Definition
    example_strategy = StrategyDefinition(
        name="RSI_SMA_Crossover_v1",
        description="Eine Beispielstrategie, die RSI und SMA-Kreuzungen verwendet.",
        buy_rules=[buy_rule1],
        sell_rules=[sell_rule1]
    )
    logger.info(f"\nErstellte Strategie-Definition: {example_strategy}")
    logger.debug(f"Strategie als Dictionary: {json.dumps(example_strategy.to_dict(), indent=2)}")

    # Teste Speichern und Laden
    temp_filepath = "temp_strategy.json"
    try:
        save_strategy_to_json(example_strategy, temp_filepath)
        loaded_strategy = load_strategy_from_json(temp_filepath)

        if loaded_strategy:
            logger.info(f"\nGeladene Strategie-Definition: {loaded_strategy}")
            logger.debug(f"Geladene Strategie als Dictionary: {json.dumps(loaded_strategy.to_dict(), indent=2)}")
            # Einfacher Vergleich (für einen echten Test bräuchte man __eq__ Methoden)
            if example_strategy.name == loaded_strategy.name and \
               len(example_strategy.buy_rules) == len(loaded_strategy.buy_rules):
                logger.info("Speichern und Laden der Strategie scheint funktioniert zu haben (Basis-Check).")
            else:
                logger.error("Fehler beim Speichern/Laden: Namen oder Regelanzahl stimmen nicht überein.")
        else:
            logger.error("Fehler: Strategie konnte nicht geladen werden.")

    except Exception as e:
        logger.error(f"Fehler im Speicher/Lade-Test: {e}", exc_info=True)
    finally:
        # Temporäre Datei löschen
        import os
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
            logger.debug(f"Temporäre Datei '{temp_filepath}' gelöscht.")

    logger.info("\n--- Test des StrategyDefinition-Moduls beendet ---")
