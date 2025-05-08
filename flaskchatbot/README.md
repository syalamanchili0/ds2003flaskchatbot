# DS2002 Environmental Chatbot

A Flask chatbot that answers:

- **COVID-19 stats** (live from api.covid19tracker.ca)  
- **GHG emissions** (local CSV → ETL → SQLite)  

Publicly hosted on a GCP VM at:  
👉 http://35.236.243.163:5000/

---

## Features

- **Live API**: pull the latest COVID numbers by province  
- **Local ETL**: ingest `gas_emissions_canada.csv`, pivot & clean into `ghg` table  
- **/chat endpoint**: POST JSON `{"question":…}` → bot reply  
- **Error handling**: clear messages on missing data, bad requests, or service issues  

---

## Repo Structure
/
├─ flaskchatbot/
│ ├─ etl.py # ETL for GHG (CSV → SQLite)
│ ├─ main.py # Flask app: / and /chat
│ ├─ requirements.txt
│ └─ gas_emissions_canada.csv
├─ reflection.pdf # 2-page writeup (requirements + learnings)
└─ README.md

---

## Local Setup

1. **Clone**  
   ```bash
   git clone https://github.com/syalamanchili0/ds2003flaskchatbot.git
   cd ds2003flaskchatbot/flaskchatbot
2. **Virtualenv**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
4. **Install**
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
5. **Run**
   ```bash
   python main.py
   # or with Gunicorn:
   gunicorn --bind 0.0.0.0:5000 main:app
6. **Test**
Browser → http://localhost:5000/

Chat →
  ```bash
curl -X POST http://localhost:5000/chat \
     -H "Content-Type: application/json" \
     -d '{"question":"COVID ON"}'
```

NEED TO FINISH REST OF README FILE
   
