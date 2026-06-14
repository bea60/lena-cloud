import os
import json
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import requests

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
WEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

MEMORY_FILE = "memory.json"

DEFAULT_MEMORY = {
    "people": {
        "Bea": "A felhasználó.",
        "Ági": "Bea párja.",
        "Baba": "Másik nevén Yoda, egy sphynx cica."
    },
    "preferences": {
        "nyelv": "Léna mindig magyarul válaszol.",
        "stílus": "Kedvesen, röviden, természetesen válaszol.",
        "kód": "Bea azt szereti, ha teljes, egyben cserélhető kódot kap."
    },
    "projects": {
        "telefonos Léna": "Bea telefonos AI asszisztenst épít Android appban, Railway backenddel és GitHub mentéssel."
    },
    "facts": [
        "Bea építi a telefonos Léna projektet.",
        "Léna telefonon fut Android appban.",
        "Léna tud időjárást, internetes keresést, híreket és árfolyamokat keresni."
    ],
    "events": []
}


def get_weather(city="Petah Tikva"):
    try:
        if not WEATHER_API_KEY:
            return "Hiányzik az OPENWEATHER_API_KEY a Railway változók közül."

        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=hu"
        )

        r = requests.get(url, timeout=10)
        data = r.json()

        if r.status_code != 200:
            return f"Nem találtam időjárást erre a városra: {city}."

        temp = round(data["main"]["temp"])
        feels = round(data["main"].get("feels_like", data["main"]["temp"]))
        desc = data["weather"][0]["description"]
        name = data.get("name", city)

        return f"{name} városában most {temp} fok van, {desc}. Hőérzet: {feels} fok."

    except Exception as e:
        print("WEATHER HIBA:", e)
        return "Most nem sikerült lekérnem az időjárást."


def extract_city_simple(message):
    text = message.strip()
    lower = text.lower()

    # Magyar ragok levágása egyszerűen: Tel Avivban -> Tel Aviv, Budapesten -> Budapest
    patterns = [
        r"(?:idő|ido|időjárás|idojaras).*?(?:van|lesz)?\s+(.+?)(?:ban|ben|on|en|ön|n)?\??$",
        r"(?:milyen|mennyi).*?\s+(.+?)(?:ban|ben|on|en|ön|n)?\??$",
        r"(?:és|es)\s+(.+?)(?:ban|ben|on|en|ön|n)?\??$",
    ]

    for p in patterns:
        m = re.search(p, lower, re.IGNORECASE)
        if m:
            city = m.group(1).strip()
            city = re.sub(r"\b(milyen|mennyi|az|a|idő|ido|időjárás|idojaras|most|van|lesz|ott)\b", "", city, flags=re.IGNORECASE).strip()
            city = city.strip(" ?.!,:;")
            city = re.sub(r"(ban|ben|on|en|ön|n)$", "", city, flags=re.IGNORECASE).strip()
            if city and len(city) >= 2:
                return city.title()

    # Ha nem talál várost, marad Bea alapvárosa
    return "Petah Tikva"


def extract_city_with_ai(message):
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Feladatod: a felhasználó magyar mondatából csak a város nevét add vissza. "
                        "Ha nincs benne város, válaszolj pontosan ezzel: Petah Tikva. "
                        "Ne írj magyarázatot, csak a város nevét. "
                        "Példák: 'Milyen idő van Tel Avivban?' -> Tel Aviv; "
                        "'Budapesten milyen idő van?' -> Budapest; "
                        "'És Eilatban?' -> Eilat."
                    )
                },
                {"role": "user", "content": message}
            ],
            temperature=0
        )
        city = response.choices[0].message.content.strip()
        city = city.replace(".", "").strip()
        if city:
            return city
    except Exception as e:
        print("CITY AI HIBA:", e)

    return extract_city_simple(message)


def is_weather_question(message):
    lower = message.lower()
    words = ["idő", "ido", "időjárás", "idojaras", "hány fok", "hany fok", "meleg", "hideg", "esik", "eső", "eso"]
    return any(w in lower for w in words)


def is_internet_question(message):
    lower = message.lower()
    keywords = [
        "keress", "keresd", "nézz utána", "nezz utana", "interneten", "google",
        "friss", "aktuális", "aktualis", "hír", "hir", "hírek", "hirek",
        "mai hír", "mai hir", "mai hírek", "mai hirek", "fő hír", "fo hir",
        "mi történt", "mi tortent", "izraelben", "világban", "vilagban",
        "most mennyi", "árfolyam", "arfolyam", "bitcoin", "ethereum",
        "sport", "meccs", "ki nyerte", "eredmény", "eredmeny"
    ]
    return any(k in lower for k in keywords)


def internet_search(message):
    try:
        response = client.responses.create(
            model="gpt-4o-mini",
            tools=[{"type": "web_search_preview"}],
            input=[
                {
                    "role": "system",
                    "content": (
                        "Te Léna vagy, Bea kedves magyar AI asszisztense. "
                        "Használj élő internetes keresést friss hírekhez, árfolyamhoz, sporthoz és aktuális adatokhoz. "
                        "Magyarul válaszolj, röviden és érthetően."
                    )
                },
                {"role": "user", "content": message}
            ]
        )
        if hasattr(response, "output_text") and response.output_text:
            return response.output_text
        return "Találtam találatokat, de most nem sikerült szépen összefoglalnom."
    except Exception as e:
        print("WEB SEARCH HIBA:", e)
        return "Most nem sikerült interneten keresnem."



def today_text():
    return datetime.now().strftime("%Y-%m-%d")


def normalize_memory(memory):
    if not isinstance(memory, dict):
        memory = {}

    result = {
        "people": {},
        "preferences": {},
        "projects": {},
        "facts": [],
        "events": []
    }

    for key in ["people", "preferences", "projects"]:
        result[key].update(DEFAULT_MEMORY.get(key, {}))

    for key in ["facts", "events"]:
        result[key].extend(DEFAULT_MEMORY.get(key, []))

    # Régi memory.json támogatása
    if isinstance(memory.get("memories"), list):
        for item in memory["memories"]:
            if item and item not in result["facts"]:
                result["facts"].append(item)

    for key in ["people", "preferences", "projects"]:
        if isinstance(memory.get(key), dict):
            result[key].update(memory[key])

    for key in ["facts", "events"]:
        if isinstance(memory.get(key), list):
            for item in memory[key]:
                if item and item not in result[key]:
                    result[key].append(item)

    result["facts"] = result["facts"][-120:]
    result["events"] = result["events"][-200:]
    return result


def load_memory():
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return normalize_memory(saved)
        except Exception as e:
            print("MEMORY LOAD HIBA:", e)

    return normalize_memory(DEFAULT_MEMORY)


def save_memory(memory):
    memory = normalize_memory(memory)
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def memory_text():
    memory = load_memory()
    lines = []

    lines.append("SZEMÉLYEK:")
    for name, desc in memory.get("people", {}).items():
        lines.append(f"- {name}: {desc}")

    lines.append("\\nPREFERENCIÁK:")
    for key, value in memory.get("preferences", {}).items():
        lines.append(f"- {key}: {value}")

    lines.append("\\nPROJEKTEK:")
    for key, value in memory.get("projects", {}).items():
        lines.append(f"- {key}: {value}")

    lines.append("\\nFONTOS TÉNYEK:")
    for fact in memory.get("facts", [])[-60:]:
        lines.append(f"- {fact}")

    lines.append("\\nESEMÉNYEK:")
    for event in memory.get("events", [])[-40:]:
        lines.append(f"- {event}")

    return "\\n".join(lines)


def add_fact(text):
    memory = load_memory()
    text = text.strip()
    if text and text not in memory["facts"]:
        memory["facts"].append(text)
    save_memory(memory)


def add_event(text):
    memory = load_memory()
    event = f"{today_text()}: {text.strip()}"
    if event not in memory["events"]:
        memory["events"].append(event)
    save_memory(memory)


def add_person(name, description):
    memory = load_memory()
    memory["people"][name.strip()] = description.strip()
    save_memory(memory)


def add_preference(key, value):
    memory = load_memory()
    memory["preferences"][key.strip()] = value.strip()
    save_memory(memory)


def add_project(key, value):
    memory = load_memory()
    memory["projects"][key.strip()] = value.strip()
    save_memory(memory)


def remember_smart(fact):
    original = fact.strip()
    lower = original.lower()

    m = re.match(r"^([A-ZÁÉÍÓÖŐÚÜŰ][\\wÁÉÍÓÖŐÚÜŰáéíóöőúüű\\- ]{1,30})\\s+(az|egy)\\s+(.+)$", original)
    if m:
        name = m.group(1).strip()
        desc = m.group(3).strip()
        add_person(name, desc)
        add_event(f"Új személy/emlék mentve: {name} - {desc}")
        return "Megjegyeztem. 💜"

    if "szeretem" in lower or "kedvenc" in lower or "jobban szeretem" in lower:
        add_preference(f"preferencia {today_text()}", original)
        add_event(f"Új preferencia mentve: {original}")
        return "Megjegyeztem a preferenciád. 💜"

    if "projekt" in lower or "léna" in lower or "railway" in lower or "github" in lower:
        add_project(f"projekt emlék {today_text()}", original)
        add_event(f"Projekt emlék mentve: {original}")
        return "Megjegyeztem a Léna projekthez. 💜"

    add_fact(original)
    add_event(f"Új emlék mentve: {original}")
    return "Megjegyeztem. 💜"


def is_memory_question(message):
    lower = message.lower()
    keywords = [
        "emlékszel", "emlekszel", "mit tudsz rólam", "mit tudsz rolam",
        "mit jegyeztél meg", "mit jegyeztel meg", "ki az a", "ki az",
        "min dolgoztunk", "mik az emlékeid", "mik az emlekeid",
        "memória", "memoria"
    ]
    return any(k in lower for k in keywords)


def answer_from_memory(message):
    memories = memory_text()
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Te Léna vagy. Csak az alábbi hosszú távú memóriából válaszolj. "
                        "Ha nincs benne a válasz, mondd meg röviden, hogy ezt még nem jegyezted meg. "
                        "Magyarul, kedvesen válaszolj.\\n\\n"
                        f"HOSSZÚ TÁVÚ MEMÓRIA:\\n{memories}"
                    )
                },
                {"role": "user", "content": message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print("MEMORY ANSWER HIBA:", e)
        return "Most nem sikerült elővennem az emlékeimet."


def auto_memory_check(user_message, assistant_answer):
    try:
        prompt = (
            "Döntsd el, van-e ebben a beszélgetésben hosszú távon hasznos emlék. "
            "Csak JSON-t adj vissza ilyen formában: "
            "{\\"save\\": true/false, \\"type\\": \\"fact/event/preference/project/person\\", \\"key\\": \\"...\\", \\"value\\": \\"...\\"} "
            "Csak akkor ments, ha hónapok múlva is hasznos lehet. "
            "Ne ments átmeneti vagy jelentéktelen dolgokat."
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Felhasználó: {user_message}\\nLéna válasza: {assistant_answer}"}
            ],
            temperature=0
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)

        if not data.get("save"):
            return

        mtype = data.get("type", "fact")
        key = str(data.get("key", "")).strip()
        value = str(data.get("value", "")).strip()

        if not value:
            return

        if mtype == "person" and key:
            add_person(key, value)
        elif mtype == "preference" and key:
            add_preference(key, value)
        elif mtype == "project" and key:
            add_project(key, value)
        elif mtype == "event":
            add_event(value)
        else:
            add_fact(value)

    except Exception as e:
        print("AUTO MEMORY HIBA:", e)


def extract_memory_request(message):
    triggers = [
        "jegyezd meg, hogy",
        "jegyezd meg hogy",
        "emlékezz rá, hogy",
        "emlékezz rá hogy",
        "mentsd el, hogy",
        "mentsd el hogy",
        "ne felejtsd el, hogy",
        "ne felejtsd el hogy"
    ]

    lower = message.lower()

    for trigger in triggers:
        if trigger in lower:
            index = lower.find(trigger)
            fact = message[index + len(trigger):].strip()
            return fact.strip(".! ")

    return None


HTML = """
<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Léna</title>

<style>
html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    overflow: hidden;
    font-family: Arial, sans-serif;
    background: #f7efff;
    color: #241628;
}

#app {
    width: 100%;
    height: 100%;
    display: flex;
    flex-direction: column;
}

.topbar {
    background: #231417;
    color: white;
    padding: 18px 20px;
    font-size: 32px;
    font-weight: bold;
}

.hero {
    background: #3b0754;
    color: white;
    text-align: center;
    padding: 28px 20px;
    border-bottom-left-radius: 34px;
    border-bottom-right-radius: 34px;
}

.hero-title {
    font-size: 42px;
    font-weight: bold;
}

.hero-sub {
    font-size: 20px;
}

#chat {
    flex: 1;
    padding: 18px;
    overflow-y: auto;
    padding-bottom: 130px;
}

.bubble {
    background: white;
    padding: 18px 22px;
    border-radius: 24px;
    margin: 12px 0;
    font-size: 21px;
    line-height: 1.35;
    box-shadow: 0 8px 22px rgba(80, 30, 100, 0.08);
    white-space: pre-wrap;
}

.user {
    background: #e7dcff;
    margin-left: 45px;
    text-align: right;
}

.lena {
    background: white;
    margin-right: 45px;
}

.inputbar {
    position: fixed;
    bottom: 62px;
    left: 0;
    right: 0;
    background: white;
    padding: 12px;
    display: flex;
    gap: 8px;
    box-shadow: 0 -8px 22px rgba(80, 30, 100, 0.08);
}

#text {
    flex: 1;
    border: 1px solid #ddd;
    border-radius: 26px;
    padding: 15px;
    font-size: 20px;
    outline: none;
}

.sendBtn {
    border: 0;
    border-radius: 50%;
    width: 58px;
    height: 58px;
    background: #7b22ff;
    color: white;
    font-size: 28px;
}

.bottomButtons {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 62px;
    background: #ffffff;
    display: flex;
    justify-content: space-around;
    align-items: center;
    box-shadow: 0 -4px 18px rgba(80, 30, 100, 0.10);
}

.bottomButtons button {
    border: 0;
    border-radius: 20px;
    padding: 10px 14px;
    background: #3b0754;
    color: white;
    font-size: 15px;
}

#memoryPanel {
    display: none;
    position: fixed;
    left: 14px;
    right: 14px;
    bottom: 140px;
    background: white;
    border-radius: 24px;
    padding: 18px;
    box-shadow: 0 0 30px rgba(0,0,0,0.25);
    z-index: 20;
}

#memoryPanel textarea {
    width: 100%;
    height: 90px;
    font-size: 18px;
    border-radius: 18px;
    padding: 12px;
    box-sizing: border-box;
}

#memoryPanel button {
    margin-top: 10px;
    border: 0;
    border-radius: 20px;
    padding: 12px 16px;
    background: #7b22ff;
    color: white;
    font-size: 17px;
}
</style>
</head>

<body>

<div id="app">

    <div class="topbar">Léna</div>

    <div class="hero">
        <div class="hero-title">Léna 💜</div>
        <div class="hero-sub">A te személyes AI asszisztensed</div>
    </div>

    <div id="chat">
        <div class="bubble lena">Szia Bea, Léna vagyok. Itt vagyok veled. 💜</div>
    </div>

    <div id="memoryPanel">
        <b>Mit jegyezzek meg?</b><br><br>
        <textarea id="memoryText" placeholder="P
