import os
import json
import re
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import requests

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
WEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")
MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
MEMORY_FILE = os.environ.get("LENA_MEMORY_FILE", "memory.json")

DEFAULT_MEMORIES = [
    "A felhasználó Bea.",
    "Léna telefonon fut Android alkalmazásban.",
    "Léna magyarul, kedvesen és röviden válaszol."
]

def normalize_memory_item(text):
    return re.sub(r"\s+", " ", (text or "")).strip(" .!;\n\t")[:500]

def _empty_store():
    return {"memories": DEFAULT_MEMORIES.copy(), "moods": [], "updated_at": None}

def load_memory():
    data = _empty_store()
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                saved_memories = saved.get("memories", [])
                if isinstance(saved_memories, list):
                    existing = {x.casefold() for x in data["memories"]}
                    for item in saved_memories:
                        item = normalize_memory_item(item)
                        if item and item.casefold() not in existing:
                            data["memories"].append(item)
                            existing.add(item.casefold())
                moods = saved.get("moods", [])
                if isinstance(moods, list):
                    data["moods"] = moods[-365:]
                data["updated_at"] = saved.get("updated_at")
        except Exception as e:
            print("MEMÓRIA OLVASÁSI HIBA:", e)
    return data

def save_memory(data):
    data["memories"] = data.get("memories", [])[-200:]
    data["moods"] = data.get("moods", [])[-365:]
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def add_memory(text):
    text = normalize_memory_item(text)
    if not text:
        return False
    data = load_memory()
    if text.casefold() in {x.casefold() for x in data["memories"]}:
        return False
    data["memories"].append(text)
    save_memory(data)
    return True

def forget_memory(text):
    needle = normalize_memory_item(text).casefold()
    if not needle:
        return 0
    data = load_memory()
    old = data["memories"]
    kept = [x for x in old if needle not in x.casefold()]
    removed = len(old) - len(kept)
    data["memories"] = kept
    if removed:
        save_memory(data)
    return removed

def memory_text():
    return "\n".join(f"- {m}" for m in load_memory()["memories"])

def add_mood(mood, emoji="💜", note=""):
    mood = normalize_memory_item(mood)
    note = normalize_memory_item(note)
    if not mood:
        return None
    data = load_memory()
    entry = {
        "date": datetime.now().date().isoformat(),
        "time": datetime.now().strftime("%H:%M"),
        "mood": mood,
        "emoji": emoji or "💜",
        "note": note
    }
    data["moods"].append(entry)
    save_memory(data)
    return entry

def mood_for_date(target_date):
    moods = [m for m in load_memory().get("moods", []) if m.get("date") == target_date.isoformat()]
    return moods[-1] if moods else None

def detect_mood(message):
    lower = message.lower().strip()
    rules = [
        (r"\b(ma\s+)?nem\s+vagyok\s+jól\b", "nem jól", "😔"),
        (r"\b(ma\s+)?rosszul\s+vagyok\b", "rosszul", "😔"),
        (r"\b(ma\s+)?szomorú\s+vagyok\b", "szomorú", "😢"),
        (r"\b(ma\s+)?fáradt\s+vagyok\b", "fáradt", "😴"),
        (r"\b(ma\s+)?mérges\s+vagyok\b", "mérges", "😠"),
        (r"\b(ma\s+)?boldog\s+vagyok\b", "boldog", "😊"),
        (r"\b(ma\s+)?jól\s+vagyok\b", "jól", "😊"),
    ]
    for pattern, mood, emoji in rules:
        if re.search(pattern, lower, re.IGNORECASE):
            return mood, emoji
    return None

def extract_memory_request(message):
    triggers = ["jegyezd meg, hogy", "jegyezd meg hogy", "jegyezd meg", "emlékezz rá, hogy", "emlékezz rá hogy", "mentsd el, hogy", "mentsd el hogy", "ne felejtsd el, hogy", "ne felejtsd el hogy"]
    lower = message.lower()
    for trigger in triggers:
        pos = lower.find(trigger)
        if pos >= 0:
            return normalize_memory_item(message[pos + len(trigger):])
    return None

def extract_forget_request(message):
    triggers = ["felejtsd el, hogy", "felejtsd el hogy", "töröld a memóriából, hogy", "töröld a memóriából hogy", "ne emlékezz arra, hogy", "ne emlékezz arra hogy"]
    lower = message.lower()
    for trigger in triggers:
        pos = lower.find(trigger)
        if pos >= 0:
            return normalize_memory_item(message[pos + len(trigger):])
    return None

def is_weather_question(message):
    lower = message.lower()
    return any(w in lower for w in ["időjárás", "idojaras", "hány fok", "hany fok", "meleg van", "hideg van", "esik az eső", "esik az eso"])

def extract_city_simple(message):
    lower = message.lower()
    for city in ["petah tikva", "tel aviv", "jerusalem", "jeruzsálem", "haifa", "eilat"]:
        if city in lower:
            return city.title()
    return "Petah Tikva"

def get_weather(city="Petah Tikva"):
    try:
        if not WEATHER_API_KEY:
            return "Az időjárás-kulcs nincs beállítva a szerveren."
        r = requests.get("https://api.openweathermap.org/data/2.5/weather", params={"q": city, "appid": WEATHER_API_KEY, "units": "metric", "lang": "hu"}, timeout=10)
        data = r.json()
        if r.status_code != 200:
            return f"Nem találtam időjárást erre a városra: {city}."
        temp = round(data["main"]["temp"])
        feels = round(data["main"].get("feels_like", data["main"]["temp"]))
        desc = data["weather"][0]["description"]
        return f"{data.get('name', city)} városában most {temp} fok van, {desc}. Hőérzet: {feels} fok."
    except Exception as e:
        print("WEATHER HIBA:", e)
        return "Most nem sikerült lekérnem az időjárást."

HTML = """<!doctype html><html lang='hu'><head><meta charset='utf-8'><title>Léna</title></head><body style='font-family:Arial;padding:30px'><h1>Léna 💜</h1><p>A szerver működik.</p></body></html>"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "LENA", "version": "2.0", "time": datetime.now().isoformat(timespec="seconds")})

@app.route("/memory", methods=["GET"])
def memory_api():
    data = load_memory()
    return jsonify({"memories": data["memories"], "updated_at": data.get("updated_at")})

@app.route("/memory", methods=["POST"])
def memory_add_api():
    payload = request.get_json() or {}
    text = normalize_memory_item(payload.get("text", ""))
    if not text:
        return jsonify({"ok": False, "message": "Nincs mit megjegyezni."}), 400
    added = add_memory(text)
    return jsonify({"ok": True, "added": added, "message": "Megjegyeztem. 💜" if added else "Ezt már tudtam. 💜"})

@app.route("/memory/forget", methods=["POST"])
def memory_forget_api():
    payload = request.get_json() or {}
    text = normalize_memory_item(payload.get("text", ""))
    if not text:
        return jsonify({"ok": False, "message": "Nincs megadva, mit felejtsek el."}), 400
    return jsonify({"ok": True, "removed": forget_memory(text)})

@app.route("/mood", methods=["GET", "POST"])
def mood_api():
    if request.method == "GET":
        return jsonify({"moods": load_memory().get("moods", [])})
    payload = request.get_json() or {}
    entry = add_mood(payload.get("mood", ""), payload.get("emoji", "💜"), payload.get("note", ""))
    if not entry:
        return jsonify({"ok": False, "message": "Nincs megadva hangulat."}), 400
    return jsonify({"ok": True, "entry": entry})

@app.route("/ask", methods=["POST"])
def ask():
    payload = request.get_json() or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"answer": "Írj valamit, és válaszolok. 💜"})

    lower = message.lower()
    if "hogy voltam tegnap" in lower or "hogy éreztem magam tegnap" in lower:
        m = mood_for_date(datetime.now().date() - timedelta(days=1))
        return jsonify({"answer": f"Tegnap azt jegyeztem fel, hogy {m['emoji']} {m['mood']} voltál. 💜" if m else "Tegnapról még nincs hangulatbejegyzésem."})
    if "hogy vagyok ma" in lower or "hogy voltam ma" in lower:
        m = mood_for_date(datetime.now().date())
        return jsonify({"answer": f"Ma azt jegyeztem fel, hogy {m['emoji']} {m['mood']} vagy. 💜" if m else "Mára még nincs hangulatbejegyzésem."})

    forget = extract_forget_request(message)
    if forget:
        removed = forget_memory(forget)
        return jsonify({"answer": "Elfelejtettem. 💜" if removed else "Nem találtam ilyen emléket."})

    fact = extract_memory_request(message)
    if fact:
        mood = detect_mood(fact)
        if mood:
            add_mood(mood[0], mood[1], fact)
        added = add_memory(fact)
        if mood:
            if mood[0] == "jól":
                return jsonify({"answer": "Örülök, hogy ma jól vagy. Megjegyeztem. 💜"})
            return jsonify({"answer": "Megjegyeztem, hogyan érzed magad ma. 💜"})
        return jsonify({"answer": "Megjegyeztem. 💜" if added else "Ezt már tudtam. 💜"})

    mood = detect_mood(message)
    if mood:
        add_mood(mood[0], mood[1], message)

    if is_weather_question(message):
        return jsonify({"answer": get_weather(extract_city_simple(message))})

    try:
        memories = memory_text()
        recent_moods = load_memory().get("moods", [])[-7:]
        mood_context = "\n".join(f"- {m.get('date')}: {m.get('emoji','')} {m.get('mood','')}" for m in recent_moods)
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": (
                    "Te Léna vagy, egy kedves magyar AI asszisztens. Mindig magyarul válaszolj, hacsak a felhasználó más nyelvet nem kér. "
                    "Válaszolj természetesen, röviden és melegen. Ne találj ki személyes tényeket. "
                    "A tartós emlékek:\n" + memories + "\n\nAz utóbbi hangulatbejegyzések:\n" + mood_context
                )},
                {"role": "user", "content": message}
            ]
        )
        answer = (response.choices[0].message.content or "").strip() or "Nem kaptam választ."
        return jsonify({"answer": answer})
    except Exception as e:
        print("HIBA:", repr(e))
        return jsonify({"answer": "Most nem sikerült válaszolnom. A szerver naplójában látszik a pontos hiba."}), 200

# Kompatibilitás régebbi HTML-verziókkal.
@app.route("/chat", methods=["POST"])
def chat_compat():
    result = ask()
    if isinstance(result, tuple):
        return result
    data = result.get_json() if hasattr(result, "get_json") else {}
    return jsonify({"reply": data.get("answer", "Nem kaptam választ.")})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
