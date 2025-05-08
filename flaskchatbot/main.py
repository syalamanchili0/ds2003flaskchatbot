import os
import sqlite3
import pandas as pd
import requests
from flask import Flask, request, jsonify
from etl import etl_ghg, etl_covid

# Work from this file’s directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# Database and CSV file paths
DB_PATH  = os.path.join(BASE_DIR, 'data.db')
CSV_PATH = os.path.join(BASE_DIR, 'gas_emissions_canada.csv')

app = Flask(__name__)

def get_covid_report_for_province(province_code):
    """Fetch the latest COVID report via live API for a given province code."""
    url = f"https://api.covid19tracker.ca/reports/province/{province_code.lower()}"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        return {"error": "No data returned for that province."}
    latest = data[-1]
    return {
        "date":             latest.get("date","N/A"),
        "total_cases":      latest.get("total_cases",0),
        "active_cases":     latest.get("total_hospitalizations",0),
        "total_fatalities": latest.get("total_fatalities",0),
        "deaths":           latest.get("total_fatalities",0)
    }

def load_cleaned_ghg():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT * FROM ghg", conn)
    conn.close()
    return df

def initialize():
    # Always rebuild the GHG table locally
    print("🔄 Running GHG ETL…")
    etl_ghg()
    print("✔️ GHG ETL complete.")

@app.route('/', methods=['GET'])
def home():
    return (
        "🌍 Welcome to the DS2002 Environmental Chatbot!  "
        "POST JSON {'question':…} or {'message':…} to /chat"
    )

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get('question') or data.get('message') or '').strip().lower()
    if not msg:
        return jsonify(error="Please include 'question' or 'message'"), 400

    # ——— COVID logic: always use live API
    if any(k in msg for k in ('covid','case','death')):
        for prov in ["on","qc","bc","ab","mb","sk","ns","nb","nl","pe","nt","yt","nu"]:
            if prov in msg:
                res = get_covid_report_for_province(prov)
                if 'error' in res:
                    return jsonify(error=res['error']), 500
                return jsonify(answer=(
                    f"As of {res['date']}, {prov.upper()} has "
                    f"{res['total_cases']} total cases, {res['active_cases']} active, "
                    f"{res['deaths']} deaths."
                ))
        return jsonify(error="Please specify a province code (e.g., ON, QC, BC)."), 400

    # ——— GHG logic: local ETL’d CSV → SQLite
    if 'emission' in msg or 'ghg' in msg:
        df = load_cleaned_ghg()
        for prov in df['province'].str.lower().unique():
            if prov in msg:
                latest = df['year'].max()
                val = df.loc[
                    (df['province'].str.lower()==prov)&(df['year']==latest),
                    'emissions'
                ].iloc[0]
                return jsonify(answer=f"In {latest}, {prov.upper()} emitted {val} Mt CO₂e.")
        # aggregate fallback
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT year, SUM(emissions) AS total FROM ghg GROUP BY year ORDER BY year"
        ).fetchall()
        conn.close()
        lines = [f"{yr}: {tot:.1f} Mt" for yr,tot in rows]
        return jsonify(answer="GHG by year:\n" + "\n".join(lines))

    return jsonify(answer="Try asking about COVID or GHG emissions in a Canadian province.")

if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
