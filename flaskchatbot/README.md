# DS2002 Environmental Chatbot
Group Name: import numpy

Group Members: Natalie Siewick, Haley Mitchell, Srujana Yalamanchili, Vivian Jiang, and Alexa Lathom

A Flask chatbot that answers:

- **COVID-19 stats** (live from api.covid19tracker.ca)  
- **GHG emissions** (local CSV → ETL → SQLite)  

Publicly hosted on a GCP VM at:  
👉 http://35.236.243.163:5000/


## Repo Structure
/
├─ flaskchatbot/
│ ├─ etl.py # ETL for GHG (CSV → SQLite)
│ ├─ main.py # Flask app: / and /chat
│ ├─ requirements.txt
│ └─ gas_emissions_canada.csv
├─ Reflection.pdf # 2-page writeup (requirements + learnings)
├─ Bonus Bot
└─ README.md
