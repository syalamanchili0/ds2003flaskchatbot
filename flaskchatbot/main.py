import os
import sqlite3
import pandas as pd
from flask import Flask, request, jsonify
from covid_api import get_covid_report_for_province
from etl import etl_ghg, etl_covid

DB_PATH = 'data.db'
CLEAN_CSV = 'gas_emissions_canada.csv'  # raw CSV used by ETL; cleaned data loaded into SQLite
def load_cleaned_ghg():
    # After ETL, GHG data lives in SQLite 'ghg' table
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql('SELECT * FROM ghg', conn)
    conn.close()
    return df

app = Flask(__name__)

# Run ETL once
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
    return "🌍 Welcome to the DS2002 Environmental Chatbot! POST JSON {'question':...} or {'message':...} to /chat"

# Chat route
@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get('question') or data.get('message') or '').strip().lower()
    if not msg:
        return jsonify(error="Please include 'question' or 'message'"), 400

    # COVID logic: live API or DB summary
    if any(k in msg for k in ('covid','case','death')):
        # check for province code
        for prov in ["on","qc","bc","ab","mb","sk","ns","nb","nl","pe","nt","yt","nu"]:
            if prov in msg:
                res = get_covid_report_for_province(prov)
                if 'error' in res:
                    return jsonify(error=res['error']), 500
                return jsonify(answer=(f"As of {res['date']}, {prov.upper()} has {res['total_cases']} total cases, {res['active_cases']} active, {res['deaths']} deaths."))
        # fallback to national DB
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT date,total_cases,total_fatalities FROM covid_stats ORDER BY date DESC LIMIT 1").fetchone()
        conn.close()
        if row:
            d,c,f = row
            return jsonify(answer=f"As of {d[:10]}: {c} cases, {f} fatalities.")
        return jsonify(answer="No COVID data available.")

    # GHG logic: local CSV via ETL loaded table
    if 'emission' in msg or 'ghg' in msg:
        df = load_cleaned_ghg()
        for prov in df['province'].str.lower().unique():
            if prov in msg:
                latest = df['year'].max()
                val = df.loc[(df['province'].str.lower()==prov)&(df['year']==latest),'emissions'].iloc[0]
                return jsonify(answer=f"In {latest}, {prov.upper()} emitted {val} Mt CO₂e.")
        # fallback aggregate
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT year, SUM(emissions) as total FROM ghg GROUP BY year ORDER BY year").fetchall()
        conn.close()
        lines = [f"{yr}: {tot:.1f} Mt" for yr,tot in rows]
        return jsonify(answer="GHG by year:\n"+"\n".join(lines))

    return jsonify(answer="Try asking about COVID or GHG emissions in a Canadian province.")

if __name__ == '__main__':
    # make sure ETL ran
    initialize()
    port = int(os.environ.get('PORT',5000))
    app.run(host='0.0.0.0', port=port)
