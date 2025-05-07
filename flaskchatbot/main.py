import os, sqlite3
from flask import Flask, request, jsonify
from etl import etl_ghg, etl_covid

DB_PATH = 'data.db'
app = Flask(__name__)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True)
    if not data or 'question' not in data:
        return jsonify(error="Please POST JSON with a 'question' field"), 400

    q = data['question'].lower()
    conn = sqlite3.connect(DB_PATH)

    # COVID answer
    if any(term in q for term in ('covid','case','death')):
        df = conn.execute(
            "SELECT date,total_cases,total_fatalities FROM covid ORDER BY date DESC LIMIT 1"
        ).fetchall()
        if not df:
            ans = "No COVID data available."
        else:
            d,c,f = df[0]
            ans = f"As of {d[:10]}: {c} cases, {f} fatalities."

    # GHG answer
    elif 'emission' in q or 'ghg' in q:
        rows = conn.execute(
            "SELECT year, SUM(emissions) FROM ghg GROUP BY year ORDER BY year"
        ).fetchall()
        ans = "\n".join(f"{year}: {ems:.1f} Mt" for year,ems in rows)

    else:
        ans = "I only handle COVID or GHG questions."

    conn.close()
    return jsonify(answer=ans)

if __name__ == '__main__':
    try:
        etl_ghg()
        etl_covid()
        print("✔️ ETL complete, launching Flask...")
    except Exception as e:
        print(" ETL failed:", e)

    # Then start the server
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

