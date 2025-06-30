# Financial Analysis Tool

Dieses Projekt ist ein Python-basiertes Tool für Finanzmarktdatenanalyse, Backtesting und Forward Testing von Handelsstrategien.

## Funktionen

- **Datenabruf:** Abrufen von Finanzmarktdaten für Aktien, Indizes und ETFs von Yahoo Finance.
- **Handelsstrategien:** Definieren und Anwenden verschiedener Handelsstrategien basierend auf technischen Indikatoren (MA Crossover, RSI).
- **Backtesting:** Testen von Strategien anhand historischer Daten, Berechnung von Performance-Metriken und Visualisierung der Ergebnisse.
- **Forward Testing (Paper Trading):** Simulation von Handelsstrategien mit einem simulierten Datenfeed.
- **GUI:** Eine benutzerfreundliche, plattformübergreifende grafische Benutzeroberfläche mit `CustomTkinter`.

## Installation und Ausführung

1.  **Repository klonen:**
    ```bash
    git clone <repository_url>
    cd financial-analysis-tool
    ```
2.  **Virtuelle Umgebung erstellen und aktivieren:**
    ```bash
    python -m venv venv
    # Windows
    # venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```
3.  **Abhängigkeiten installieren:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Anwendung starten:**
    ```bash
    python main.py
    ```
    (Stellen Sie sicher, dass eine grafische Umgebung verfügbar ist.)

## Benötigte Bibliotheken

Eine Liste der benötigten Bibliotheken finden Sie in der Datei `requirements.txt`. Hauptbibliotheken sind:
`yfinance`, `pandas`, `numpy`, `matplotlib`, `customtkinter`.

## Verpackung als eigenständige Anwendung (.exe)

Das Projekt kann mithilfe von `PyInstaller` in eine eigenständige Anwendung verpackt werden.

1.  **PyInstaller installieren:**
    ```bash
    pip install pyinstaller
    ```
2.  **(Optional) UPX installieren:**
    UPX kann die Größe der resultierenden Datei reduzieren. Laden Sie es von [UPX GitHub Releases](https://upx.github.io/) herunter und stellen Sie sicher, dass es im System-PATH ist.

3.  **Spezifikationsdatei anpassen (`finance_tool_pyinstaller.spec`):**
    Die Datei `finance_tool_pyinstaller.spec` enthält Konfigurationen für PyInstaller. Besonders der Pfad zu den `customtkinter` Assets unter `datas` muss ggf. an Ihre lokale `venv`-Struktur angepasst werden:
    ```python
    # Beispielhafter Eintrag in datas in der .spec Datei:
    # ('venv/lib/python3.12/site-packages/customtkinter/', 'customtkinter/'),
    ```
    Sie können den korrekten Pfad zu `customtkinter` in Ihrer aktiven Umgebung mit folgendem Python-Code finden und ihn in die `.spec`-Datei eintragen:
    ```python
    import customtkinter
    print(customtkinter.__path__[0])
    ```
    Das Icon `assets/app_icon.ico` wird ebenfalls referenziert. Erstellen Sie dieses oder entfernen Sie den Verweis in der `.spec`-Datei.

4.  **Anwendung mit PyInstaller bauen:**
    Führen Sie PyInstaller im Hauptverzeichnis des Projekts aus:
    ```bash
    pyinstaller finance_tool_pyinstaller.spec
    ```

5.  **Ergebnis finden:**
    Die gebündelte Anwendung befindet sich im Ordner `dist/FinanceAnalysisTool_Bundle`. Der Ordner enthält die `.exe`-Datei (z.B. `FinanceAnalysisTool.exe`) und alle notwendigen Abhängigkeiten.

**Hinweise zur Verpackung:**
*   Wenn `console=False` in der `.spec`-Datei gesetzt ist (empfohlen für GUI-Anwendungen), werden Fehler beim Start der `.exe` nicht in einer Konsole angezeigt. Setzen Sie es zum Debuggen temporär auf `console=True`.
*   Das Bündeln von Python-Anwendungen, insbesondere mit GUI-Bibliotheken und Datendateien (wie Matplotlib), kann komplex sein. Versteckte Importe (`hiddenimports`) und das korrekte Einbinden von Datendateien (`datas`) sind oft die Hauptquellen für Probleme. Die bereitgestellte `.spec`-Datei versucht, die häufigsten Probleme für dieses Projekt zu adressieren.
*   Testen Sie die erstellte `.exe` gründlich auf einem System, das keine Entwicklungsumgebung für Python hat, um sicherzustellen, dass alle Abhängigkeiten korrekt gebündelt wurden.
