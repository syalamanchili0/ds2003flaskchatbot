import os
import sqlite3
import pandas as pd
import requests
from flask import Flask, request, jsonify
from etl import etl_ghg, etl_covid

# Make sure we run from this file’s directory so relative paths resolve correctly
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
        "date":             latest.get("date", "N/A"),
        "total_cases":      latest.get("total_cases", 0),
        "active_cases":     latest.get("total_hospitalizations", 0),
        "total_fatalities": latest.get("total_fatalities", 0),
        "deaths":           latest.get("total_fatalities", 0)
    }

def load_cleaned_ghg():
    """Read the GHG table from SQLite (populated by etl_ghg)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        df = pd.read_sql("SELECT * FROM ghg", conn)
    finally:
        conn.close()
    return df

def initialize():
    """Run both ETL pipelines at startup so tables always exist and are fresh."""
    print("🔄 Running GHG ETL...")
    etl_ghg()
    print("✔️ GHG ETL complete.")
    print("🔄 Running COVID ETL...")
    etl_covid()
    print("✔️ COVID ETL complete.")

@app.route('/', methods=['GET'])
def home():
    return (
        "🌍 Welcome to the DS2002 Environmental Chatbot!  "
        "POST JSON {'question':...} or {'message':...} to /chat"
    )

@app.route('/chat', methods=['POST'])
def chat():
    payload = request.get_json(silent=True) or {}
    msg = (payload.get('question') or payload.get('message') or '').strip().lower()
    if not msg:
        return jsonify(error="Please include 'question' or 'message'"), 400

    # — COVID logic: live API per‐province, else national from SQLite
    if any(k in msg for k in ('covid','case','death')):
        # per‐province live API
        for prov in ["on","qc","bc","ab","mb","sk","ns","nb","nl","pe","nt","yt","nu"]:
            if prov in msg:
                try:
                    res = get_covid_report_for_province(prov)
                except Exception as e:
                    return jsonify(error=f"COVID API error: {e}"), 500
                if 'error' in res:
                    return jsonify(error=res['error']), 500
                return jsonify(answer=(
                    f"As of {res['date']}, {prov.upper()} has "
                    f"{res['total_cases']} cases, {res['active_cases']} active, "
                    f"{res['deaths']} deaths."
                ))
        # fallback: national summary from SQLite
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT date, total_cases, total_fatalities "
                "FROM covid_stats ORDER BY date DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        if row:
            d,c,f = row
            return jsonify(answer=f"As of {d[:10]}: {c} cases, {f} fatalities.")
        return jsonify(answer="No COVID data available.")

    # — GHG logic: per‐province from SQLite, else aggregate
    if 'emission' in msg or 'ghg' in msg:
        df = load_cleaned_ghg()
        for prov in df['province'].str.lower().unique():
            if prov in msg:
                latest = int(df['year'].max())
                val = df.loc[
                    (df['province'].str.lower()==prov)&(df['year']==latest),
                    'emissions'
                ].iloc[0]
                return jsonify(answer=f"In {latest}, {prov.upper()} emitted {val} Mt CO₂e.")
        # fallback: aggregate across all provinces
        conn = sqlite3.connect(DB_PATH)
        try:
            rows = conn.execute(
                "SELECT year, SUM(emissions) as total FROM ghg GROUP BY year ORDER BY year"
            ).fetchall()
        finally:
            conn.close()
        lines = [f"{yr}: {tot:.1f} Mt" for yr,tot in rows]
        return jsonify(answer="GHG by year:\n" + "\n".join(lines))

    # — fallback for unrecognized questions
    return jsonify(answer="Try asking about COVID or GHG emissions in a Canadian province.")

if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
