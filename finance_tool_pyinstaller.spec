# finance_tool_pyinstaller.spec

# Dieser Block analysiert die Hauptskript-Datei und deren Importe.
a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # CustomTkinter benötigt seine Assets. PyInstaller findet diese oft, aber explizit ist sicherer.
        # Der Pfad muss relativ zum Speicherort dieser .spec-Datei sein oder absolut.
        # Finde den Pfad zu customtkinter im site-packages Verzeichnis.
        ('venv/lib/python3.12/site-packages/customtkinter/', 'customtkinter/'),
        # Matplotlib benötigt seine Datendateien (mpl-data)
        # Muss ggf. angepasst werden, je nachdem wo `matplotlib` installiert ist.
        # ('path/to/your/venv/Lib/site-packages/matplotlib/mpl-data', 'mpl-data')
    ],
    hiddenimports=[
        'pandas', 'numpy', 'yfinance',
        'matplotlib', 'customtkinter',
        'tkinter', 'PIL',
        # Manchmal müssen Backend-Module für Matplotlib explizit angegeben werden:
        'matplotlib.backends.backend_tkagg',
        # Importe, die von yfinance oder anderen Bibliotheken dynamisch geladen werden könnten:
        'requests', 'platformdirs', 'pytz', 'frozendict', 'peewee', 'beautifulsoup4', 'html5lib', 'lxml'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0, # 0, 1, oder 2. 0 ist am schnellsten für Tests.
)

# Diese Sektion beschreibt, wie die .exe-Datei erstellt wird.
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='FinanceAnalysisTool', # Name der resultierenden .exe-Datei
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True, # UPX-Komprimierung, falls UPX installiert ist
    console=False, # False für GUI-Anwendungen, True für Konsolenanwendungen
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/app_icon.ico' # Optional: Pfad zu einer .ico Datei für das App-Icon
                                # Erstelle ein Dummy-Icon, falls nicht vorhanden.
)

# Diese Sektion beschreibt, wie alle Dateien in einem Ordner gesammelt werden (one-folder bundle).
# Für eine einzelne .exe-Datei (one-file bundle) sind Anpassungen nötig,
# aber one-folder ist oft robuster für den Anfang.
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='FinanceAnalysisTool_Bundle' # Name des Ausgabeordners
)

# Hinweis:
# 1. Pfade in `datas`: Der Pfad zu `customtkinter` (und ggf. `matplotlib/mpl-data`)
#    muss an die lokale Entwicklungsumgebung (insbesondere das venv) angepasst werden.
#    Eine bessere Methode wäre, den Pfad dynamisch mit `import customtkinter; customtkinter.__path__[0]`
#    zu ermitteln und hier einzusetzen oder ein Hook-Skript zu verwenden.
#
# 2. Icon: Ein Icon `assets/app_icon.ico` wird erwartet. Wenn nicht vorhanden,
#    entfernen Sie die `icon=` Zeile oder erstellen Sie ein Icon.
#
# 3. UPX: Wenn UPX nicht installiert ist, setzen Sie `upx=False` in EXE und COLLECT.
#
# 4. Console: Für GUI-Anwendungen `console=False`. Wenn beim Start Fehler auftreten,
#    kann es hilfreich sein, temporär `console=True` zu setzen, um Fehlermeldungen in der Konsole zu sehen.
#
# Verwendung:
# 1. Stellen Sie sicher, dass PyInstaller installiert ist: `pip install pyinstaller`
# 2. (Optional) Installieren Sie UPX für kleinere Exe-Dateien.
# 3. Passen Sie die Pfade in dieser .spec-Datei an (insbesondere für `customtkinter`).
# 4. Führen Sie PyInstaller mit dieser .spec-Datei aus dem Projekt-Root-Verzeichnis aus:
#    `pyinstaller finance_tool_pyinstaller.spec`
# 5. Die gebündelte Anwendung befindet sich dann im `dist/FinanceAnalysisTool_Bundle` Ordner.
#
# Beispiel für dynamische Pfadermittlung für `datas` (außerhalb der .spec, zur Vorbereitung):
# import customtkinter
# import matplotlib
# customtkinter_path = (customtkinter.__path__[0], 'customtkinter/')
# matplotlib_datapath = (matplotlib.get_data_path(), 'mpl-data/')
# Diese müssten dann manuell in die .spec Datei oben eingetragen werden oder die .spec Datei
# wird durch ein Python Skript generiert.
#
# Für Matplotlib ist es oft besser, wenn PyInstaller die Daten automatisch findet.
# Falls nicht, kann man es wie oben gezeigt explizit hinzufügen.
# Die `hiddenimports` sind oft der Schlüssel zum Erfolg.
#
# Testen Sie die erstellte .exe gründlich, da Abhängigkeiten manchmal schwer zu fassen sind.
