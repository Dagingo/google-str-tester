# finance_tool/data_fetcher.py

import yfinance as yf
import pandas as pd

def fetch_data(ticker_symbol: str, start_date: str, end_date: str, interval: str = "1d") -> pd.DataFrame | None:
    """
    Ruft historische Finanzmarktdaten für einen bestimmten Ticker ab.

    Args:
        ticker_symbol (str): Das Tickersymbol (z.B. "AAPL" für Apple, "^GDAXI" für DAX).
        start_date (str): Das Startdatum im Format "YYYY-MM-DD".
        end_date (str): Das Enddatum im Format "YYYY-MM-DD".
        interval (str, optional): Das Datenintervall (z.B. "1d", "1wk", "1mo", "1h"). Standard ist "1d".

    Returns:
        pd.DataFrame | None: Ein Pandas DataFrame mit den Daten (OHLC, Volumen, Dividenden, Aktiensplits)
                             oder None bei einem Fehler.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(start=start_date, end=end_date, interval=interval)
        if data.empty:
            print(f"Keine Daten für {ticker_symbol} im angegebenen Zeitraum gefunden.")
            return None
        return data
    except Exception as e:
        print(f"Fehler beim Abrufen der Daten für {ticker_symbol}: {e}")
        return None

def fetch_multiple_tickers(ticker_list: list[str], start_date: str, end_date: str, interval: str = "1d") -> dict[str, pd.DataFrame]:
    """
    Ruft historische Finanzmarktdaten für eine Liste von Tickern ab.

    Args:
        ticker_list (list[str]): Eine Liste von Tickersymbolen.
        start_date (str): Das Startdatum im Format "YYYY-MM-DD".
        end_date (str): Das Enddatum im Format "YYYY-MM-DD".
        interval (str, optional): Das Datenintervall. Standard ist "1d".

    Returns:
        dict[str, pd.DataFrame]: Ein Dictionary, bei dem die Schlüssel die Tickersymbole sind
                                 und die Werte die entsprechenden DataFrames.
    """
    all_data = {}
    for ticker_symbol in ticker_list:
        data = fetch_data(ticker_symbol, start_date, end_date, interval)
        if data is not None:
            all_data[ticker_symbol] = data
    return all_data

def get_stock_info(ticker_symbol: str) -> dict | None:
    """
    Ruft allgemeine Informationen zu einer Aktie ab.

    Args:
        ticker_symbol (str): Das Tickersymbol.

    Returns:
        dict | None: Ein Dictionary mit Aktieninformationen oder None bei einem Fehler.
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        return ticker.info
    except Exception as e:
        print(f"Fehler beim Abrufen der Aktieninformationen für {ticker_symbol}: {e}")
        return None

# --- Beispiel für die Verwendung ---
if __name__ == "__main__":
    # Manueller Modus Beispiel
    print("--- Manueller Modus Beispiel ---")
    # Beispiel: Aktie (Apple)
    aapl_data = fetch_data("AAPL", "2023-01-01", "2023-12-31")
    if aapl_data is not None:
        print("\nApple (AAPL) Daten (letzte 5 Tage):")
        print(aapl_data.tail())

    # Beispiel: Index (DAX)
    dax_data = fetch_data("^GDAXI", "2023-01-01", "2023-12-31")
    if dax_data is not None:
        print("\nDAX (^GDAXI) Daten (letzte 5 Tage):")
        print(dax_data.tail())

    # Beispiel: ETF (SPDR S&P 500 ETF)
    spy_data = fetch_data("SPY", "2023-01-01", "2023-12-31", interval="1wk")
    if spy_data is not None:
        print("\nSPDR S&P 500 ETF (SPY) Daten (wöchentlich, letzte 5 Einträge):")
        print(spy_data.tail())

    # Automatischer Modus Beispiel (hier simuliert durch vordefinierte Ticker)
    print("\n--- Automatischer Modus Beispiel (vordefinierte Ticker) ---")
    watchlist_tickers = ["MSFT", "GOOGL", "TSLA"] # Beispiel für eine Watchlist
    automatic_data = fetch_multiple_tickers(watchlist_tickers, "2023-11-01", "2023-12-31")
    for ticker, data_df in automatic_data.items():
        print(f"\nDaten für {ticker} (letzte 5 Tage):")
        print(data_df.tail())

    # Beispiel: Aktieninformationen
    print("\n--- Aktieninformationen Beispiel ---")
    msft_info = get_stock_info("MSFT")
    if msft_info:
        print(f"\nInformationen für Microsoft (MSFT):")
        print(f"  Name: {msft_info.get('longName')}")
        print(f"  Sektor: {msft_info.get('sector')}")
        print(f"  Branche: {msft_info.get('industry')}")
        print(f"  Land: {msft_info.get('country')}")
        print(f"  Webseite: {msft_info.get('website')}")
        # print(msft_info) # Gibt alle verfügbaren Informationen aus

    # Beispiel für einen nicht existierenden Ticker oder Fehler
    print("\n--- Fehlerbeispiel ---")
    invalid_data = fetch_data("NICHTEXISTENT", "2023-01-01", "2023-01-31")
    if invalid_data is None:
        print("Abruf für NICHTEXISTENT erwartungsgemäß fehlgeschlagen.")

    # Beispiel für Datenabruf mit stündlichem Intervall (Achtung: Yahoo Finance hat Einschränkungen für Intraday-Daten)
    # Für längere Zeiträume mit Intraday-Daten kann es sein, dass nur die letzten ~60 Tage verfügbar sind.
    print("\n--- Intraday Beispiel (letzte Tage) ---")
    aapl_intraday = fetch_data("AAPL", "2024-07-10", "2024-07-17", interval="1h")
    if aapl_intraday is not None:
        print("\nApple (AAPL) Intraday Daten (1h, letzte 5 Einträge):")
        print(aapl_intraday.tail())
    else:
        print("Keine Intraday-Daten für AAPL abrufbar oder Zeitraum zu lang.")

    # Abrufen von Dividenden und Aktiensplits (sind im normalen .history() DataFrame enthalten)
    if aapl_data is not None:
        dividends = aapl_data[aapl_data['Dividends'] > 0]
        if not dividends.empty:
            print("\nApple (AAPL) Dividenden 2023:")
            print(dividends['Dividends'])

        splits = aapl_data[aapl_data['Stock Splits'] > 0]
        if not splits.empty:
            print("\nApple (AAPL) Aktiensplits 2023:")
            print(splits['Stock Splits'])
