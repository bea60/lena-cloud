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
MOOD_FILE = "mood.json"
CHAT_FILE = "chat_history.json"
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MAX_HISTORY = 20

DEFAULT_MEMORIES = [
    "A felhasználó Bea.",
    "Ági Bea párja.",
    "Bea építi a telefonos Léna projektet.",
    "Léna telefonon fut Android appban.",
    "Baba, másik nevén Yoda, egy sphynx cica.",
    "Bea azt szereti, ha teljes, egyben cserélhető kódot kap.",
    "Léna magyarul, kedvesen, röviden válaszol."
]

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
    return "Petah Tikva"

def extract_city_with_ai(message):
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "A felhasználó magyar mondatából csak a város nevét add vissza. "
                        "Ha nincs benne város, válaszolj pontosan ezzel: Petah Tikva."
                    )
                },
                {"role": "user", "content": message}
            ],
            temperature=0
        )
        city = response.choices[0].message.content.strip().replace(".", "")
        if city:
            return city
    except Exception as e:
        print("CITY AI HIBA:", e)
    return extract_city_simple(message)

def is_weather_question(message):
    lower = message.lower()
    words = ["idő", "ido", "időjárás", "idojaras", "hány fok", "hany fok", "meleg", "hideg", "esik", "eső", "eso"]
    return any(w in lower for w in words)

def normalize_memory_item(text):
    text = re.sub(r"\s+", " ", (text or "")).strip(" .!;")
    return text[:500]

def load_memory():
    memory = {"memories": DEFAULT_MEMORIES.copy(), "updated_at": None}
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            items = saved.get("memories", [])
            for item in items:
                item = normalize_memory_item(item)
                if item and item.casefold() not in {x.casefold() for x in memory["memories"]}:
                    memory["memories"].append(item)
            memory["updated_at"] = saved.get("updated_at")
        except Exception as e:
            print("MEMÓRIA OLVASÁSI HIBA:", e)
    return memory

def save_memory(memory):
    memory["memories"] = memory.get("memories", [])[-100:]
    memory["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)

def add_memory(text):
    text = normalize_memory_item(text)
    if not text:
        return False
    memory = load_memory()
    items = memory.get("memories", [])
    if text.casefold() in {x.casefold() for x in items}:
        return False
    items.append(text)
    memory["memories"] = items[-100:]
    save_memory(memory)
    return True

def forget_memory(text):
    needle = normalize_memory_item(text).casefold()
    if not needle:
        return 0
    memory = load_memory()
    old = memory.get("memories", [])
    kept = [x for x in old if needle not in x.casefold()]
    removed = len(old) - len(kept)
    memory["memories"] = kept
    if removed:
        save_memory(memory)
    return removed

def memory_text():
    return "\n".join(f"- {m}" for m in load_memory().get("memories", []))

def extract_memory_request(message):
    triggers = [
        "jegyezd meg, hogy", "jegyezd meg hogy",
        "emlékezz rá, hogy", "emlékezz rá hogy",
        "mentsd el, hogy", "mentsd el hogy",
        "ne felejtsd el, hogy", "ne felejtsd el hogy"
    ]
    lower = message.lower()
    for trigger in triggers:
        if trigger in lower:
            index = lower.find(trigger)
            return normalize_memory_item(message[index + len(trigger):])
    return None

def extract_forget_request(message):
    triggers = [
        "felejtsd el, hogy", "felejtsd el hogy",
        "töröld a memóriából, hogy", "töröld a memóriából hogy",
        "ne emlékezz arra, hogy", "ne emlékezz arra hogy"
    ]
    lower = message.lower()
    for trigger in triggers:
        if trigger in lower:
            index = lower.find(trigger)
            return normalize_memory_item(message[index + len(trigger):])
    return None


def load_json_file(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"JSON OLVASÁSI HIBA ({path}):", e)
        return default

def save_json_file(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)

def load_chat():
    data = load_json_file(CHAT_FILE, {"messages": []})
    messages = data.get("messages", [])
    if not isinstance(messages, list):
        messages = []
    return messages[-MAX_HISTORY:]

def save_chat(messages):
    save_json_file(CHAT_FILE, {
        "messages": messages[-MAX_HISTORY:],
        "updated_at": datetime.now().isoformat(timespec="seconds")
    })

def remember_chat(role, content):
    messages = load_chat()
    messages.append({"role": role, "content": str(content)[:4000]})
    save_chat(messages)

def load_moods():
    data = load_json_file(MOOD_FILE, {"moods": []})
    moods = data.get("moods", [])
    return moods if isinstance(moods, list) else []

def add_mood(mood, emoji="💜"):
    moods = load_moods()
    item = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "mood": normalize_memory_item(mood),
        "emoji": (emoji or "💜")[:4]
    }
    moods.append(item)
    save_json_file(MOOD_FILE, {"moods": moods[-100:]})
    return item

def recent_mood_text():
    moods = load_moods()
    if not moods:
        return "Nincs hangulatbejegyzés."
    latest = moods[-1]
    return f"Legutóbbi hangulat: {latest.get('date', '')} – {latest.get('emoji', '💜')} {latest.get('mood', '')}"

def auto_memory_candidate(message):
    """Csak egyértelmű, tartós személyes tényeket próbál meg kinyerni."""
    lower = message.casefold()
    skip = (
        "mi az", "ki az", "hogyan", "miért", "mikor", "mennyi", "milyen",
        "időjárás", "idő van", "hány fok", "keress", "nézd meg"
    )
    if any(x in lower for x in skip):
        return None
    triggers = (
        "szeretem ", "nem szeretem ", "a kedvencem ", "utálom ",
        "azt szeretem, ha ", "általában ", "mindig "
    )
    if any(t in lower for t in triggers) and 8 <= len(message) <= 220:
        return normalize_memory_item(message)
    return None

# A telefonos alkalmazás külön HTML fájlt használ az Android assets mappából.
# Ez a minimális kezdőoldal csak böngészős teszthez van.
HTML = """<!doctype html><html lang="hu"><head><meta charset="utf-8"><title>Léna</title></head>
<body style="font-family:Arial;padding:30px"><h1>Léna 💜</h1><p>A szerver működik.</p></body></html>"""

@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "name": "Léna",
        "version": "3.0",
        "model": MODEL,
        "time": datetime.now().isoformat(timespec="seconds")
    })

@app.route("/mood", methods=["GET"])
def mood_get():
    return jsonify({"moods": load_moods()})

@app.route("/mood", methods=["POST"])
def mood_post():
    data = request.get_json() or {}
    mood = normalize_memory_item(data.get("mood", ""))
    emoji = data.get("emoji", "💜")
    if not mood:
        return jsonify({"ok": False, "message": "Nincs megadva hangulat."}), 400
    return jsonify({"ok": True, "item": add_mood(mood, emoji)})

@app.route("/history", methods=["GET"])
def history_get():
    return jsonify({"messages": load_chat()})

@app.route("/history/clear", methods=["POST"])
def history_clear():
    save_chat([])
    return jsonify({"ok": True})

@app.route("/memory", methods=["GET"])
def memory_api():
    memory = load_memory()
    return jsonify({
        "memories": memory.get("memories", []),
        "updated_at": memory.get("updated_at")
    })

@app.route("/memory", methods=["POST"])
def memory_add_api():
    data = request.get_json() or {}
    text = normalize_memory_item(data.get("text", ""))
    if not text:
        return jsonify({"ok": False, "message": "Nincs mit megjegyezni."}), 400
    added = add_memory(text)
    return jsonify({"ok": True, "added": added, "message": "Megjegyeztem. 💜" if added else "Ezt már tudtam. 💜"})

@app.route("/memory/forget", methods=["POST"])
def memory_forget_api():
    data = request.get_json() or {}
    text = normalize_memory_item(data.get("text", ""))
    if not text:
        return jsonify({"ok": False, "message": "Nincs megadva, mit felejtsek el."}), 400
    removed = forget_memory(text)
    return jsonify({"ok": True, "removed": removed})

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"answer": "Írj valamit, és válaszolok. 💜"})

    remember_chat("user", message)

    forget = extract_forget_request(message)
    if forget:
        removed = forget_memory(forget)
        answer = "Elfelejtettem. 💜" if removed else "Nem találtam ilyen emléket."
        remember_chat("assistant", answer)
        return jsonify({"answer": answer})

    fact = extract_memory_request(message)
    if fact:
        added = add_memory(fact)
        answer = "Megjegyeztem. 💜" if added else "Ezt már tudtam. 💜"
        remember_chat("assistant", answer)
        return jsonify({"answer": answer})

    if is_weather_question(message):
        city = extract_city_with_ai(message)
        answer = get_weather(city)
        remember_chat("assistant", answer)
        return jsonify({"answer": answer})

    auto_fact = auto_memory_candidate(message)
    if auto_fact:
        add_memory(auto_fact)

    memories = memory_text()
    history = load_chat()[:-1][-12:]

    system_prompt = (
        "Te Léna vagy, Bea személyes magyar AI asszisztense. "
        "Mindig magyarul válaszolj, természetesen, kedvesen és tömören. "
        "Használd a rendelkezésre álló emlékeket, de ne találj ki személyes tényeket. "
        "Ha valami bizonytalan vagy ellentmondásos, kérdezz vissza. "
        "Ne mondd azt, hogy emlékszel valamire, ha nincs az emlékek vagy a beszélgetés között. "
        "A felhasználó kifejezett 'jegyezd meg' kéréseit a rendszer külön elmenti. "
        "Ha a kérdés a mai napra vagy a közelmúltra utal, a beszélgetési előzményeket is vedd figyelembe.\n\n"
        "HOSSZÚ TÁVÚ EMLÉKEK:\n" + memories + "\n\n" +
        "HANGULATNAPLÓ:\n" + recent_mood_text()
    )

    try:
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": message})

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            temperature=0.7
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            answer = "Most nem kaptam használható választ."
        remember_chat("assistant", answer)
        return jsonify({"answer": answer})

    except Exception as e:
        print("HIBA:", e)
        answer = "Most nem sikerült válaszolnom. Nézd meg a Railway logot."
        remember_chat("assistant", answer)
        return jsonify({"answer": answer}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
