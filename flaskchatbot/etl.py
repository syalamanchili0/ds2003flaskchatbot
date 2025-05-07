import pandas as pd
import sqlite3
import requests

CSV_PATH = 'gas_emissions_canada.csv'
DB_PATH  = 'data.db'
COVID_API = 'https://api.covid19tracker.ca/reports'

def etl_ghg():
    """Extract & transform the GHG CSV, then load to SQLite."""
    # Extract
    df = pd.read_csv(CSV_PATH)
    # Transform: pivot long, clean types
    df = df.rename(columns={
        'Full Name':'full_name','1990':'y1990','2005':'y2005','2022':'y2022'
    })[['province','full_name','y1990','y2005','y2022']]
    long = df.melt(
        id_vars=['province','full_name'],
        value_vars=['y1990','y2005','y2022'],
        var_name='year', value_name='emissions'
    )
    long['year'] = long['year'].str.lstrip('y').astype(int)
    long['emissions'] = pd.to_numeric(long['emissions'], errors='coerce')
    long.dropna(subset=['emissions'], inplace=True)

    # Load
    conn = sqlite3.connect(DB_PATH)
    long.to_sql('ghg', conn, if_exists='replace', index=False)
    conn.close()

def etl_covid():
    """Extract & transform the COVID API, then load to SQLite."""
    resp = requests.get(COVID_API, timeout=10)
    resp.raise_for_status()
    payload = resp.json()
    df = pd.DataFrame(payload.get('data', []))
    if 'province' not in df:
        df['province'] = payload.get('province','All')
    keep = ['date','province','total_cases','total_fatalities',
            'total_recoveries','total_vaccinations']
    df = df[[c for c in keep if c in df]].copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    for c in keep[2:]:
        df[c] = df[c].fillna(0).astype(int)

    # Load
    conn = sqlite3.connect(DB_PATH)
    df.to_sql('covid', conn, if_exists='replace', index=False)
    conn.close()

if __name__=='__main__':
    try:
        etl_ghg()
        etl_covid()
        print("ETL successful.")
    except Exception as e:
        print("ETL error:", e)

