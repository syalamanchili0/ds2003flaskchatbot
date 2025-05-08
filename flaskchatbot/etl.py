import pandas as pd
from sqlalchemy import create_engine
import requests

CSV_PATH = 'gas_emissions_canada.csv'
DB_URI   = 'sqlite:///data.db'
COVID_API = 'https://api.covid19tracker.ca/reports'

def etl_ghg():
    """Extract & transform the GHG CSV, then load to SQLite."""
    try:
        df = pd.read_csv(CSV_PATH)
    except FileNotFoundError as e:
        raise FileNotFoundError(f"GHG CSV not found at {CSV_PATH}") from e

    df = (
        df.rename(columns={
            'Full Name':'full_name',
            '1990':'y1990',
            '2005':'y2005',
            '2022':'y2022'
        })[
            ['province','full_name','y1990','y2005','y2022']
        ]
    )
    long = df.melt(
        id_vars=['province','full_name'],
        value_vars=['y1990','y2005','y2022'],
        var_name='year', value_name='emissions'
    )
    long['year'] = long['year'].str.lstrip('y').astype(int)
    long['emissions'] = pd.to_numeric(long['emissions'], errors='coerce')
    long.dropna(subset=['emissions'], inplace=True)

    engine = create_engine(DB_URI)
    long.to_sql('ghg', engine, if_exists='replace', index=False)
    
def etl_covid():
    resp = requests.get(COVID_API, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    df = pd.DataFrame(payload.get('data', []))
    df['province'] = payload.get('province', 'All')
    cols = ['date','province','total_cases','total_fatalities',
            'total_recoveries','total_vaccinations']
    df = df[[c for c in cols if c in df.columns]].copy()
    df['date'] = pd.to_datetime(df['date'], errors='coerce')
    for c in cols[2:]:
        df[c] = df[c].fillna(0).astype(int)
    df.sort_values(['province','date'], inplace=True)
    df['new_cases'] = df.groupby('province')['total_cases']\
                        .diff().fillna(0).astype(int)
    df['cases_7d_avg'] = (
        df.groupby('province')['new_cases']
          .rolling(7, min_periods=1)
          .mean()
          .reset_index(level=0, drop=True)
          .round(1)
    )
    engine = create_engine(DB_URI)
    df.to_sql('covid_stats', engine, if_exists='replace', index=False)

if __name__=='__main__':
    try:
        etl_ghg()
        print("✔️ GHG ETL complete.")
    except Exception as e:
        print("ETL error:", e)
