# main.py
import sys
import os
import logging # Import logging module

# Stelle sicher, dass das Paket 'finance_tool' im PYTHONPATH ist,
# besonders wenn main.py aus dem Hauptverzeichnis des Projekts ausgeführt wird.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# Logging-Konfiguration
# Zeitstempel - Level - Modulname - Zeilennummer - Nachricht
logging.basicConfig(level=logging.DEBUG,  # DEBUG für detaillierte Logs während der Fehlersuche
                    format='%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s',
                    handlers=[
                        logging.StreamHandler(sys.stdout) # Loggt auf Konsole
                        # Optional: logging.FileHandler("app.log", mode='w') # Loggt in eine Datei, 'w' für überschreiben bei jedem Start
                    ])
logger = logging.getLogger(__name__) # Logger für main.py

try:
    logger.debug("Versuche, FinanceApp aus finance_tool.gui zu importieren.")
    from finance_tool.gui import FinanceApp
    logger.debug("FinanceApp erfolgreich importiert.")
except ImportError as e:
    logger.error(f"Fehler beim Importieren von FinanceApp: {e}", exc_info=True)
    logger.error("Stellen Sie sicher, dass das Skript aus dem Hauptverzeichnis des Projekts ausgeführt wird,")
    logger.error("oder dass das Paket 'finance_tool' korrekt installiert/erreichbar ist.")
    logger.error(f"Aktueller sys.path: {sys.path}")
    sys.exit(1)
except Exception as e:
    logger.critical(f"Unerwarteter Fehler beim Importieren von FinanceApp: {e}", exc_info=True)
    sys.exit(1)

def main():
    """
    Hauptfunktion zum Starten der Finanzanalyse-Anwendung.
    """
    logger.info("===================================")
    logger.info("Starte Finanzanalyse-Tool...")
    logger.info(f"Python Version: {sys.version}")
    logger.info(f"Betriebssystem: {sys.platform}")
    logger.info(f"Aktuelles Arbeitsverzeichnis: {os.getcwd()}")
    logger.info(f"sys.path: {sys.path}")
    logger.info("===================================")

    # Überprüfe, ob eine Display-Umgebung vorhanden ist
    try:
        logger.debug("Überprüfe Display-Umgebung...")
        import tkinter
        try:
            root_check = tkinter.Tk()
            root_check.withdraw() # Fenster nicht anzeigen
            root_check.update_idletasks() # Verarbeite Events
            logger.debug(f"Tkinter Root-Fenster Test: Bildschirmname: {root_check.winfo_screen()}, Geometrie: {root_check.winfo_geometry()}")
            root_check.destroy()
            logger.debug("Display-Umgebung scheint vorhanden zu sein.")
        except tkinter.TclError as e:
            if "no display name" in str(e).lower() or "couldn't connect to display" in str(e).lower():
                logger.error("FEHLER: Keine Display-Umgebung gefunden (z.B. $DISPLAY Variable nicht gesetzt).")
                logger.error("Die GUI-Anwendung kann nicht ohne grafische Umgebung gestartet werden.")
                sys.exit(1)
            else:
                logger.warning(f"Anderer TclError bei Display-Prüfung: {e}", exc_info=True)
                # Fortfahren, aber es könnte später fehlschlagen
        except Exception as e:
            logger.warning(f"Unbekannter Fehler bei der Display-Prüfung mit tkinter.Tk(): {e}", exc_info=True)

    except ImportError:
        logger.critical("FEHLER: Tkinter konnte nicht importiert werden. Stellen Sie sicher, dass es installiert ist.", exc_info=True)
        sys.exit(1)
    except Exception as e:
        logger.warning(f"Allgemeiner Fehler bei der Display-Prüfung: {e}", exc_info=True)

    try:
        logger.info("Initialisiere FinanceApp...")
        app = FinanceApp()
        logger.info("FinanceApp initialisiert. Starte mainloop...")
        app.mainloop()
    except Exception as e:
        logger.critical("Kritischer Fehler in der Hauptanwendungsschleife (app.mainloop).", exc_info=True)
    finally:
        logger.info("===================================")
        logger.info("Finanzanalyse-Tool beendet.")
        logger.info("===================================")

if __name__ == "__main__":
    main()
