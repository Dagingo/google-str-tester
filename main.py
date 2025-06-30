# main.py
import sys
import os
import logging

# Stelle sicher, dass das Paket 'finance_tool' im PYTHONPATH ist
module_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if module_path not in sys.path:
    sys.path.insert(0, module_path)

# Logging-Konfiguration
logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(name)s - %(module)s:%(lineno)d - %(message)s',
                    handlers=[
                        logging.StreamHandler(sys.stdout)
                        # logging.FileHandler("app_pyqt.log", mode='w')
                    ])
logger = logging.getLogger(__name__) # Logger für main.py, oder verwende Root-Logger

# Importiere PyQt6-spezifische Teile erst nach potenziellen Pfadanpassungen
try:
    logger.debug("Versuche, PyQt6-Komponenten und FinanceApp zu importieren.")
    from PyQt6.QtWidgets import QApplication
    from finance_tool.gui import MainWindow # Die neue PyQt6 MainWindow
    logger.debug("PyQt6-Komponenten und FinanceApp erfolgreich importiert.")
except ImportError as e:
    logger.critical(f"Fehler beim Importieren notwendiger Module: {e}", exc_info=True)
    logger.critical("Stellen Sie sicher, dass PyQt6 installiert ist (pip install PyQt6) und das Projekt korrekt strukturiert ist.")
    sys.exit(1)
except Exception as e:
    logger.critical(f"Unerwarteter Fehler beim Importieren: {e}", exc_info=True)
    sys.exit(1)

def main():
    """
    Hauptfunktion zum Starten der Finanzanalyse-Anwendung mit PyQt6.
    """
    logger.info("===================================")
    logger.info("Starte Finanzanalyse-Tool (PyQt6 Version)...")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Betriebssystem: {sys.platform}")
    logger.info(f"Aktuelles Arbeitsverzeichnis: {os.getcwd()}")
    logger.info(f"sys.path: {sys.path}")
    logger.info("===================================")

    # QApplication ist für jede PyQt-Anwendung erforderlich
    # sys.argv ermöglicht Kommandozeilenargumente für Qt, falls benötigt
    app = QApplication(sys.argv)
    logger.debug("QApplication Instanz erstellt.")

    try:
        logger.info("Initialisiere MainWindow...")
        main_window = MainWindow()
        main_window.show() # Zeigt das Hauptfenster an
        logger.info("MainWindow initialisiert und angezeigt. Starte Event Loop...")

        # Startet die Qt Event Loop. Das Programm blockiert hier, bis die App geschlossen wird.
        exit_code = app.exec()
        logger.info(f"Qt Event Loop beendet mit Exit Code: {exit_code}")

    except Exception as e:
        logger.critical("Kritischer Fehler während der Ausführung der Anwendung.", exc_info=True)
        sys.exit(1) # Beende mit Fehlercode
    finally:
        logger.info("===================================")
        logger.info("Finanzanalyse-Tool (PyQt6 Version) beendet.")
        logger.info("===================================")
        sys.exit(exit_code if 'exit_code' in locals() else 0)


if __name__ == "__main__":
    main()
