# --- Imports ---
import discord
import pandas as pd
from discord.ext import commands
import requests
import jsonify

# --- SETTINGS ---
GROQ_API_KEY = ""  # Replace with your real Groq API key
DISCORD_BOT_TOKEN = ""

# --- Province Dictionary ---
PROVINCES = {
    'Alberta':'ab', 'British Columbia' : 'bc', 'Manitoba' : 'mb', 'New Brunswick':'nb',
    'Newfoundland & Labrador': 'nl', 'Nova Scotia':'ns', 'Northwest Territories'  :'nt',
    'Nunavut':'nu', 'Ontario':'on', 'Prince Edward Island':'pe', 'Quebec':'qc', 'Saskatchewan':'sk',
    'Yukon' :'yt'
}

# --- Read in API data ---
def api_data(code):
    url = f"https://api.covid19tracker.ca/reports/province/{code}"  # replace with your real API
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()  # assuming JSON response
    except Exception as e:
        print(f"API fetch error: {e}")
        return None

# --- Extract the province from the message ---
def extract_province_code(message):
    msg = message.lower()
    for name, code in PROVINCES.items():
        if name.lower() in msg:
            return code.upper()
    return None

# --- BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

# --- GROQ API FUNCTION ---

#reads in csv data
def load_context_from_csv(file_path, code):
    try:
        res = api_data(code)
        df = pd.read_csv(file_path)
        context_lines = ["Follow these rules:",
                         "- YOU CAN ONLY TAKE INFORMATION FROM THE FILE OR API PROVIDED",
                         "- Do NOT try to guess any information that is not provided",
                         "- Only include data that is relevant to what is asked by the user",
                         "- Do NOT output everything unless the user asks",
                         "- If you do not know the information, relay that",
                         "",
                         "Data:"]
        if not df.empty:
            print('hi')
            for _, row in df.iterrows():
                context_lines.append(
                    f"- {row['Full Name']}: {row['province']} : {row['1990']} ghg in 1990, {row['2005']} ghg in 2005, "
                    f"{row['2022']} ghg in 2022."
                )
        else:
            print(res.get('provinces', []))
            for p in res.get("provinces", []):
                context_lines.append(
                    f"As of {res['date']}, {p} has "
                    f"{res['total_cases']} total cases, "
                    f"{res['total_recoveries']} recoveries, and "
                    f"{res['total_fatalities']} deaths."
                )
            print(context_lines)
        return "\n".join(context_lines)

    except Exception as e:
        return "You are a helpful assistant. (Context CSV failed to load.)"

#reads in api data
def load_context_api(code):
    res = api_data(code)
    latest = res["data"][-1]

    context_lines = ["Follow these rules:",
                     "- YOU CAN ONLY TAKE INFORMATION FROM THE FILE OR API PROVIDED",
                     "- Do NOT try to guess any information that is not provided",
                     "- Only include data that is relevant to what is asked by the user",
                     "- Do NOT output everything unless the user asks",
                     "- If you do not know the information, relay that",
                     "",
                     "Data:",
                     f"As of {latest['date']}, {code} has "
                     f"{latest['total_cases']} total cases, "
                     f"{latest['total_recoveries']} recoveries, and "
                     f"{latest['total_fatalities']} deaths."]

   # print(context_lines)
    return "\n".join(context_lines)


async def ask_groq(user_message):
    code = extract_province_code(user_message)
    #reads in the data depending on whether is an API or csv
    if any(k in user_message.lower() for k in ["emission", "ghg", "carbon", 'green house gasses', 'carbon footprint',
                                               'carbon', 'air pollution']):
        system_prompt = load_context_from_csv("gas_emissions_canada.csv", code)
    else:
        system_prompt = load_context_api(code)

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        return result['choices'][0]['message']['content']
    except Exception as e:
        print(f"Groq API error: {e}")
        return "Sorry, I'm having a brain freeze. 🧊 Try again later!"

# --- UTILITY: Send Long Messages Safely ---

async def send_long_message(channel, content):
    # Send message in chunks of max 2000 characters
    for i in range(0, len(content), 2000):
        await channel.send(content[i:i+2000])

# --- EVENTS & COMMANDS ---

@bot.event
async def on_ready():
    print(f"We have logged in as {bot.user}")

@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.name}! 👋")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Uh-oh, I don't know that command! Try `!hello`.")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    # Basic keyword responses

    content = message.content.lower()

    # COVID-related
    if "covid" in content or "cases" in content or "deaths" in content:
        for provinces in ['Alberta','British Columbia','Manitoba', 'New Brunswick','Newfoundland & Labrador',
                          'Nova Scotia','Northwest Territories',
'Nunavut', 'Ontario', 'Prince Edward Island','Quebec', 'Saskatchewan', 'Yukon']:
           if provinces.lower() in content.lower():
                abbrev = PROVINCES[provinces]
                url = f"https://api.covid19tracker.ca/reports/province/{abbrev}"
                response = requests.get(url)
                response.raise_for_status()
                data = response.json()["data"][-1] # get most recent record
                if "error" in data:
                    return data["error"]
                return await message.channel.send(f"As of {data['date']}, {provinces.title()} "
                                                  f"has {data['total_cases']} "
                                                  f"total cases,"
                                                  f"{data['total_recoveries']}"
                                                  f" recovery cases, and {data['total_fatalities']} deaths.")
        return "Please specify a valid province code (e.g., ON, QC, BC)."



# GHG emissions-related
    if "emission" in content or "ghg" in content:
        df = pd.read_csv('gas_emissions_canada.csv')
        match_found = False
        print(df)
        for province in ['Alberta','British Columbia','Manitoba', 'New Brunswick','Newfoundland & Labrador',
                         'Nova Scotia','Northwest Territories',
'Nunavut', 'Ontario', 'Prince Edward Island','Quebec', 'Saskatchewan', 'Yukon']:
            for dates in ['1990', '2005', '2022']:
                if province.lower() in content.lower() and dates in content:
                    match_found = True
                    abbrev = PROVINCES[province]
                    print(abbrev)
                    value = df[
                        (df["province"].str.lower() == abbrev)
                        ][dates].values
                    print(value)


                    if value.size > 0:
                        return await message.channel.send(f"In {dates}, {province.title()} "
                                                          f"emitted {value[0]
                                                          } megatons of CO₂ equivalent.")

        if not match_found:
            await message.channel.send("Please select a Canadian province AND a date (1990,2005, 2022)")
    else:
    # Everything else: use Groq AI
        reply = await ask_groq(message.content)
        await send_long_message(message.channel, reply)
    await bot.process_commands(message)

# --- START BOT ---

bot.run(DISCORD_BOT_TOKEN)