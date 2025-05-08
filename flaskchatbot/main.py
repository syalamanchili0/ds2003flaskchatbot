import os, re, sqlite3
import pandas as pd
import requests
from flask import Flask, request, jsonify
from etl import etl_ghg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, 'data.db')

app = Flask(__name__)

# Map province codes to full names
PROVINCES = {
    'ab': 'Alberta',         'bc': 'British Columbia',
    'mb': 'Manitoba',        'nb': 'New Brunswick',
    'nl': 'Newfoundland & Labrador',
    'ns': 'Nova Scotia',     'nt': 'Northwest Territories',
    'nu': 'Nunavut',         'on': 'Ontario',
    'pe': 'Prince Edward Island',
    'qc': 'Quebec',          'sk': 'Saskatchewan',
    'yt': 'Yukon'
}

def get_covid_report_for_province(code):
    url = f"https://api.covid19tracker.ca/reports/province/{code}"
    resp = requests.get(url, timeout=10)
    try:
        resp.raise_for_status()
    except requests.HTTPError:
        return {"error": f"API error: {resp.status_code}"}
    data = resp.json().get("data", [])
    if not data:
        return {"error": "No data for that province."}
    latest = data[-1]
    tc = latest.get("total_cases", 0)
    tf = latest.get("total_fatalities", 0)
    tr = latest.get("total_recoveries", 0)
    active = tc - tf - tr
    return {
        "date": latest.get("date", "N/A"),
        "total_cases": tc,
        "active_cases": active,
        "total_recoveries": tr,
        "total_fatalities": tf
    }

def load_cleaned_ghg():
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM ghg", conn)
        conn.close()
        return df
    except Exception as e:
        app.logger.error(f"GHG load error: {e}")
        return None

@app.before_first_request
def initialize():
    app.logger.info("🔄 Running GHG ETL…")
    try:
        etl_ghg()
        app.logger.info("✔️ GHG ETL complete.")
    except Exception as e:
        app.logger.error(f"ETL failed: {e}")

@app.route('/', methods=['GET'])
def home():
    return (
        "🌍 DS2002 Environmental Chatbot<br>"
        "POST JSON {'question':…} to /chat"
    )

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get('question') or data.get('message') or "").lower()
    if not msg:
        return jsonify(error="Include 'question' or 'message'"), 400

    # COVID logic
    if any(k in msg for k in ('covid','case','death')):
        for code, name in PROVINCES.items():
            if re.search(rf"\b{code}\b", msg) or name.lower() in msg:
                res = get_covid_report_for_province(code)
                if 'error' in res:
                    return jsonify(error=res['error']), 500
                return jsonify(answer=(
                    f"As of {res['date']}, {name} has "
                    f"{res['total_cases']} total cases, "
                    f"{res['active_cases']} active cases, "
                    f"{res['total_recoveries']} recoveries, and "
                    f"{res['total_fatalities']} deaths."
                ))
        return jsonify(error="Specify a valid province code/name (e.g. ON, Ontario)."), 400

    # GHG logic
    if 'emission' in msg or 'ghg' in msg:
        df = load_cleaned_ghg()
        if df is None or df.empty:
            return jsonify(error="GHG data unavailable."), 500
        for code, name in PROVINCES.items():
            if re.search(rf"\b{code}\b", msg) or name.lower() in msg:
                year = df['year'].max()
                val  = df.loc[
                    (df['province'].str.upper()==code.upper()) &
                    (df['year']==year),
                    'emissions'
                ].iloc[0]
                return jsonify(answer=f"In {year}, {name} emitted {val:.1f} Mt CO₂e.")
        # aggregate fallback
        try:
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT year, SUM(emissions) total FROM ghg GROUP BY year ORDER BY year"
            ).fetchall()
            conn.close()
            lines = [f"{yr}: {tot:.1f} Mt" for yr, tot in rows]
            return jsonify(answer="GHG by year:\n" + "\n".join(lines))
        except Exception as e:
            app.logger.error(f"Aggregate GHG error: {e}")
            return jsonify(error="Error retrieving GHG aggregates."), 500

    return jsonify(answer="Ask me about COVID or GHG emissions in Canada."), 200

if __name__ == '__main__':
    initialize()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
