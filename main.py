# main.py
import sys
import os

# Stelle sicher, dass das Paket 'finance_tool' im PYTHONPATH ist,
# besonders wenn main.py aus dem Hauptverzeichnis des Projekts ausgeführt wird.
# Dies ist oft nicht nötig, wenn das Projekt als Paket installiert ist oder
# wenn man `python -m finance_tool.main` verwenden würde (was hier nicht der Fall ist).
# Für einen einfachen `python main.py` Aufruf aus dem Projekt-Root:
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from finance_tool.gui import FinanceApp
except ImportError as e:
    print(f"Fehler beim Importieren von FinanceApp: {e}")
    print("Stellen Sie sicher, dass das Skript aus dem Hauptverzeichnis des Projekts ausgeführt wird,")
    print("oder dass das Paket 'finance_tool' korrekt installiert/erreichbar ist.")
    print(f"Aktueller sys.path: {sys.path}")
    sys.exit(1)

def main():
    """
    Hauptfunktion zum Starten der Finanzanalyse-Anwendung.
    """
    print("Starte Finanzanalyse-Tool...")

    # Überprüfe, ob eine Display-Umgebung vorhanden ist (rudimentärer Check)
    # In einer Headless-Umgebung wird customtkinter wahrscheinlich fehlschlagen.
    try:
        # Versuche, eine Tk-Instanz zu erstellen, um frühzeitig zu scheitern, wenn kein Display vorhanden ist.
        # Dies ist nicht perfekt, da customtkinter seine eigene Initialisierung hat.
        import tkinter
        try:
            root_check = tkinter.Tk()
            root_check.destroy()
        except tkinter.TclError as e:
            if "no display name" in str(e):
                print("FEHLER: Keine Display-Umgebung gefunden (z.B. $DISPLAY Variable nicht gesetzt).")
                print("Die GUI-Anwendung kann nicht ohne grafische Umgebung gestartet werden.")
                print("Wenn Sie in einer Headless-Umgebung arbeiten (z.B. Docker ohne X11, SSH ohne -X),")
                print("kann die GUI nicht angezeigt werden.")
                sys.exit(1)
            else:
                raise # Anderer TclError

    except ImportError:
        print("FEHLER: Tkinter konnte nicht importiert werden. Stellen Sie sicher, dass es installiert ist.")
        sys.exit(1)
    except Exception as e:
        print(f"Unbekannter Fehler bei der Display-Prüfung: {e}")
        # Fortfahren, aber es könnte später fehlschlagen

    app = FinanceApp()
    app.mainloop()
    print("Finanzanalyse-Tool beendet.")

if __name__ == "__main__":
    main()
