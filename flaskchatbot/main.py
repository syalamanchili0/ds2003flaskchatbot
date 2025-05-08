# main.py

import os
import sqlite3
import pandas as pd
import requests
from flask import Flask, request, jsonify
from etl import etl_ghg, etl_covid

DB_PATH    = 'data.db'
CLEAN_CSV  = 'gas_emissions_canada.csv'

app = Flask(__name__)

def get_covid_report_for_province(province_code):
    """Get latest COVID report for a province via live API."""
    url = f"https://api.covid19tracker.ca/reports/province/{province_code.lower()}"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return {"error": "No data returned for that province."}
        latest = data[-1]
        return {
            "date":             latest.get("date","N/A"),
            "total_cases":      latest.get("total_cases","N/A"),
            "active_cases":     latest.get("total_hospitalizations","N/A"),
            "total_fatalities": latest.get("total_fatalities","N/A"),
            "deaths":           latest.get("total_fatalities","N/A")
        }
    except Exception as e:
        return {"error": str(e)}

def load_cleaned_ghg():
    """Read the GHG table from SQLite (populated by etl_ghg)."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT * FROM ghg', conn)
    conn.close()
    return df

# ETL
def initialize():
    if not os.path.exists(DB_PATH):
        try:
            etl_ghg()
        except Exception as e:
            app.logger.error(f"GHG ETL failed: {e}")
        try:
            etl_covid()
        except Exception as e:
            app.logger.error(f"COVID ETL failed: {e}")

@app.before_first_request
def before_first_request():
    initialize()

# Home route
@app.route('/', methods=['GET'])
def home():
    return ("🌍 Welcome to the DS2002 Environmental Chatbot!  "
            "POST JSON {'question':...} or {'message':...} to /chat")

# Chat route
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get('question') or data.get('message') or '').strip().lower()
    if not msg:
        return jsonify(error="Please include 'question' or 'message'"), 400

    # COVID logic (live API or SQLite fallback)
    if any(k in msg for k in ('covid','case','death')):
        for prov in ["on","qc","bc","ab","mb","sk","ns","nb","nl","pe","nt","yt","nu"]:
            if prov in msg:
                res = get_covid_report_for_province(prov)
                if 'error' in res:
                    return jsonify(error=res['error']), 500
                return jsonify(answer=(
                    f"As of {res['date']}, {prov.upper()} has "
                    f"{res['total_cases']} cases, {res['active_cases']} active, "
                    f"{res['deaths']} deaths."
                ))
        # national summary from SQLite
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT date, total_cases, total_fatalities "
            "FROM covid_stats ORDER BY date DESC LIMIT 1"
        ).fetchone()
        conn.close()
        if row:
            d,c,f = row
            return jsonify(answer=f"As of {d[:10]}: {c} cases, {f} fatalities.")
        return jsonify(answer="No COVID data available.")

    # GHG logic (local CSV/SQLite)
    if 'emission' in msg or 'ghg' in msg:
        df = load_cleaned_ghg()
        for prov in df['province'].str.lower().unique():
            if prov in msg:
                latest = df['year'].max()
                val = df.loc[
                    (df['province'].str.lower()==prov)&(df['year']==latest),
                    'emissions'
                ].iloc[0]
                return jsonify(answer=f"In {latest}, {prov.upper()} emitted {val} Mt CO₂e.")
        # fallback aggregate by year
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute(
            "SELECT year, SUM(emissions) as total FROM ghg GROUP BY year ORDER BY year"
        ).fetchall()
        conn.close()
        lines = [f"{yr}: {tot:.1f} Mt" for yr,tot in rows]
        return jsonify(answer="GHG by year:\n" + "\n".join(lines))

    return jsonify(answer="Try asking about COVID or GHG emissions in a Canadian province.")

# Launch
if __name__ == '__main__':
    initialize()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
