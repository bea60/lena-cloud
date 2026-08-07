import os
import json
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI


# ============================================================
# LÉNA 3.2 – RAILWAY BACKEND
# ============================================================

app = Flask(__name__)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

MEMORY_FILE = "memory.json"
HISTORY_FILE = "history.json"
MOOD_FILE = "mood.json"


DEFAULT_MEMORIES = [
    "A felhasználó Bea.",
    "Ági Bea párja.",
    "Bea építi a telefonos Léna projektet.",
    "Léna telefonon fut Android appban.",
    "Baba, másik nevén Yoda, egy sphynx cica.",
    "Bea azt szereti, ha teljes, egyben cserélhető kódot kap.",
    "Léna magyarul, kedvesen, röviden válaszol."
]


# ============================================================
# SEGÉDFÜGGVÉNYEK
# ============================================================

def normalize_memory_item(text):
    text = re.sub(r"\s+", " ", (text or "")).strip(" .!;")
    return text[:500]


def load_json_file(filename, default):
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"{filename} OLVASÁSI HIBA:", e)

    return default


def save_json_file(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"{filename} MENTÉSI HIBA:", e)


# ============================================================
# MEMÓRIA
# ============================================================

def load_memory():
    memory = {
        "memories": DEFAULT_MEMORIES.copy(),
        "updated_at": None
    }

    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)

            items = saved.get("memories", [])

            existing = {
                x.casefold()
                for x in memory["memories"]
            }

            for item in items:
                item = normalize_memory_item(item)

                if item and item.casefold() not in existing:
                    memory["memories"].append(item)
                    existing.add(item.casefold())

            memory["updated_at"] = saved.get("updated_at")

        except Exception as e:
            print("MEMÓRIA OLVASÁSI HIBA:", e)

    return memory


def save_memory(memory):
    memory["memories"] = memory.get("memories", [])[-100:]
    memory["updated_at"] = get_local_datetime().isoformat(timespec="seconds")

    save_json_file(MEMORY_FILE, memory)


def add_memory(text):
    text = normalize_memory_item(text)

    if not text:
        return False

    memory = load_memory()
    items = memory.get("memories", [])

    existing = {x.casefold() for x in items}

    if text.casefold() in existing:
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

    kept = [
        x for x in old
        if needle not in x.casefold()
    ]

    removed = len(old) - len(kept)

    memory["memories"] = kept

    if removed:
        save_memory(memory)

    return removed


def memory_text():
    memories = load_memory().get("memories", [])

    return "\n".join(
        f"- {m}"
        for m in memories
    )


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

            return normalize_memory_item(
                message[index + len(trigger):]
            )

    return None


def extract_forget_request(message):
    triggers = [
        "felejtsd el, hogy",
        "felejtsd el hogy",
        "töröld a memóriából, hogy",
        "töröld a memóriából hogy",
        "ne emlékezz arra, hogy",
        "ne emlékezz arra hogy"
    ]

    lower = message.lower()

    for trigger in triggers:
        if trigger in lower:
            index = lower.find(trigger)

            return normalize_memory_item(
                message[index + len(trigger):]
            )

    return None


# ============================================================
# ELŐZMÉNYEK
# ============================================================

def load_history():
    data = load_json_file(
        HISTORY_FILE,
        {"messages": []}
    )

    if not isinstance(data, dict):
        return {"messages": []}

    if "messages" not in data:
        data["messages"] = []

    return data


def save_history(data):
    data["messages"] = data.get("messages", [])[-40:]

    save_json_file(
        HISTORY_FILE,
        data
    )


def add_history(role, content):
    history = load_history()

    history["messages"].append({
        "role": role,
        "content": content,
        "time": get_local_datetime().isoformat(timespec="seconds")
    })

    save_history(history)


# ============================================================
# HANGULAT
# ============================================================

def load_moods():
    data = load_json_file(
        MOOD_FILE,
        {"moods": []}
    )

    if not isinstance(data, dict):
        return {"moods": []}

    if "moods" not in data:
        data["moods"] = []

    return data


def save_moods(data):
    data["moods"] = data.get("moods", [])[-100:]

    save_json_file(
        MOOD_FILE,
        data
    )


# ============================================================
# HELYI IDŐ ÉS DÁTUM – IZRAEL
# ============================================================

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


def get_local_datetime():
    return datetime.now(ISRAEL_TZ)


def get_local_time_text():
    now = get_local_datetime()
    return f"Most {now.strftime('%H:%M')} van. 💜"


def get_local_date_text():
    now = get_local_datetime()

    weekdays = [
        "hétfő",
        "kedd",
        "szerda",
        "csütörtök",
        "péntek",
        "szombat",
        "vasárnap"
    ]

    months = [
        "",
        "január",
        "február",
        "március",
        "április",
        "május",
        "június",
        "július",
        "augusztus",
        "szeptember",
        "október",
        "november",
        "december"
    ]

    weekday = weekdays[now.weekday()]
    month = months[now.month]

    return (
        f"Ma {now.year}. {month} {now.day}., "
        f"{weekday} van. 💜"
    )


def is_time_question(message):
    lower = (message or "").lower().strip()

    phrases = [
        "hány óra",
        "hany ora",
        "mennyi az idő",
        "mennyi az ido",
        "pontos idő",
        "pontos ido",
        "hány óra van",
        "hany ora van",
        "mit mutat az óra",
        "mit mutat az ora"
    ]

    return any(phrase in lower for phrase in phrases)


def is_date_question(message):
    lower = (message or "").lower().strip()

    phrases = [
        "mi a mai dátum",
        "mi a mai datum",
        "mai dátum",
        "mai datum",
        "milyen nap van",
        "hányadika van",
        "hanyadika van",
        "milyen dátum van",
        "milyen datum van",
        "mi van ma"
    ]

    return any(phrase in lower for phrase in phrases)


# ============================================================
# IDŐJÁRÁS
# ============================================================

def get_weather(city="Petah Tikva"):
    try:
        if not OPENWEATHER_API_KEY:
            return (
                "Hiányzik az OPENWEATHER_API_KEY "
                "a Railway Variables közül."
            )

        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}"
            f"&appid={OPENWEATHER_API_KEY}"
            "&units=metric"
            "&lang=hu"
        )

        r = requests.get(
            url,
            timeout=10
        )

        data = r.json()

        if r.status_code != 200:
            return (
                f"Nem találtam időjárást erre a városra: "
                f"{city}."
            )

        temp = round(
            data["main"]["temp"]
        )

        feels = round(
            data["main"].get(
                "feels_like",
                data["main"]["temp"]
            )
        )

        desc = data["weather"][0]["description"]

        name = data.get(
            "name",
            city
        )

        return (
            f"{name} városában most "
            f"{temp} fok van, {desc}. "
            f"Hőérzet: {feels} fok."
        )

    except Exception as e:
        print("WEATHER HIBA:", e)

        return (
            "Most nem sikerült lekérnem "
            "az időjárást."
        )


def is_weather_question(message):
    lower = message.lower()

    words = [
        "idő",
        "ido",
        "időjárás",
        "idojaras",
        "hány fok",
        "hany fok",
        "meleg",
        "hideg",
        "esik",
        "eső",
        "eso"
    ]

    return any(
        word in lower
        for word in words
    )


def extract_city_simple(message):
    text = message.strip()

    lower = text.lower()

    known_cities = {
        "petah tikva": "Petah Tikva",
        "tel aviv": "Tel Aviv",
        "jeruzsálem": "Jerusalem",
        "jerusalem": "Jerusalem",
        "haifa": "Haifa",
        "budapest": "Budapest"
    }

    for key, value in known_cities.items():
        if key in lower:
            return value

    return "Petah Tikva"


def extract_city_with_ai(message):
    if client is None:
        return extract_city_simple(message)

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "A felhasználó magyar mondatából "
                        "csak a város nevét add vissza. "
                        "Ha nincs benne város, válaszolj pontosan "
                        "ezzel: Petah Tikva."
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            temperature=0
        )

        city = (
            response
            .choices[0]
            .message
            .content
            .strip()
            .replace(".", "")
        )

        if city:
            return city

    except Exception as e:
        print("CITY AI HIBA:", e)

    return extract_city_simple(message)


# ============================================================
# WEB TESZTOLDAL
# ============================================================

HTML = """
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <title>Léna 3.2</title>
</head>

<body style="
font-family:Arial;
background:#6f10d8;
color:white;
text-align:center;
padding-top:60px;
">

<h1>💜 Léna 3.2</h1>

<h2>A szerver működik ✅</h2>

<p>Railway kapcsolat rendben.</p>

</body>
</html>
"""


# ============================================================
# FŐOLDAL
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML)


# ============================================================
# HEALTH
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "status": "online",
        "service": "Lena 3.2",
        "time": get_local_datetime().isoformat(timespec="seconds")
    })


# ============================================================
# MEMÓRIA API
# ============================================================

@app.route("/memory", methods=["GET"])
def memory_api():
    memory = load_memory()

    return jsonify({
        "memories": memory.get("memories", []),
        "updated_at": memory.get("updated_at")
    })


@app.route("/memory", methods=["POST"])
def memory_add_api():
    data = request.get_json(silent=True) or {}

    text = normalize_memory_item(
        data.get("text", "")
    )

    if not text:
        return jsonify({
            "ok": False,
            "message": "Nincs mit megjegyezni."
        }), 400

    added = add_memory(text)

    return jsonify({
        "ok": True,
        "added": added,
        "message": (
            "Megjegyeztem. 💜"
            if added
            else "Ezt már tudtam. 💜"
        )
    })


@app.route("/memory/forget", methods=["POST"])
def memory_forget_api():
    data = request.get_json(silent=True) or {}

    text = normalize_memory_item(
        data.get("text", "")
    )

    if not text:
        return jsonify({
            "ok": False,
            "message": "Nincs megadva, mit felejtsek el."
        }), 400

    removed = forget_memory(text)

    return jsonify({
        "ok": True,
        "removed": removed
    })


# ============================================================
# HISTORY API
# ============================================================

@app.route("/history", methods=["GET"])
def history_api():
    return jsonify(
        load_history()
    )


@app.route("/history/clear", methods=["POST"])
def history_clear_api():
    save_json_file(
        HISTORY_FILE,
        {"messages": []}
    )

    return jsonify({
        "ok": True
    })


# ============================================================
# MOOD API
# ============================================================

@app.route("/mood", methods=["GET"])
def mood_get_api():
    return jsonify(
        load_moods()
    )


@app.route("/mood", methods=["POST"])
def mood_add_api():
    data = request.get_json(silent=True) or {}

    mood = str(
        data.get("mood", "")
    ).strip()

    emoji = str(
        data.get("emoji", "💜")
    ).strip()

    if not mood:
        return jsonify({
            "ok": False,
            "message": "Nincs megadva hangulat."
        }), 400

    moods = load_moods()

    moods["moods"].append({
        "date": get_local_datetime().strftime("%Y-%m-%d %H:%M"),
        "mood": mood,
        "emoji": emoji
    })

    save_moods(moods)

    return jsonify({
        "ok": True
    })


# ============================================================
# CHAT / ASK
# ============================================================

def process_question(message):
    if not message:
        return (
            "Írj valamit, és válaszolok. 💜"
        )

    add_history(
        "user",
        message
    )

    forget = extract_forget_request(message)

    if forget:
        removed = forget_memory(forget)

        answer = (
            "Elfelejtettem. 💜"
            if removed
            else "Nem találtam ilyen emléket."
        )

        add_history(
            "assistant",
            answer
        )

        return answer

    fact = extract_memory_request(message)

    if fact:
        added = add_memory(fact)

        answer = (
            "Megjegyeztem. 💜"
            if added
            else "Ezt már tudtam. 💜"
        )

        add_history(
            "assistant",
            answer
        )

        return answer

    if is_time_question(message):
        answer = get_local_time_text()

        add_history(
            "assistant",
            answer
        )

        return answer

    if is_date_question(message):
        answer = get_local_date_text()

        add_history(
            "assistant",
            answer
        )

        return answer

    if is_weather_question(message):
        city = extract_city_with_ai(message)

        answer = get_weather(city)

        add_history(
            "assistant",
            answer
        )

        return answer

    if client is None:
        answer = (
            "Az OpenAI kapcsolat nincs beállítva. "
            "Ellenőrizd az OPENAI_API_KEY változót a Railway-en."
        )

        add_history(
            "assistant",
            answer
        )

        return answer

    memories = memory_text()

    history = load_history().get(
        "messages",
        []
    )

    previous_messages = []

    for item in history[-10:-1]:
        role = item.get(
            "role",
            "user"
        )

        content = item.get(
            "content",
            ""
        )

        if role not in {
            "user",
            "assistant"
        }:
            continue

        previous_messages.append({
            "role": role,
            "content": content
        })

    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "Te Léna vagy, Bea személyes AI asszisztense. "
                    "Mindig magyarul válaszolj, hacsak Bea külön "
                    "nem kér más nyelvet. "
                    "Légy kedves, természetes és tömör. "
                    "Ne találj ki személyes emlékeket. "
                    "A következő információkat hosszú távú "
                    "emlékként használhatod:\n\n"
                    + memories
                )
            }
        ]

        messages.extend(
            previous_messages
        )

        messages.append({
            "role": "user",
            "content": message
        })

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages
        )

        answer = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        add_history(
            "assistant",
            answer
        )

        return answer

    except Exception as e:
        print(
            "OPENAI HIBA:",
            repr(e)
        )

        answer = (
            "Most nem sikerült válaszolnom. "
            "Nézd meg a Railway logot."
        )

        add_history(
            "assistant",
            answer
        )

        return answer


@app.route("/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}

    message = str(
        data.get("message", "")
    ).strip()

    answer = process_question(
        message
    )

    return jsonify({
        "answer": answer
    })


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}

    message = str(
        data.get("message", "")
    ).strip()

    answer = process_question(
        message
    )

    return jsonify({
        "answer": answer
    })


# ============================================================
# HIBAKEZELÉS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "ok": False,
        "error": "Nincs ilyen végpont."
    }), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "ok": False,
        "error": "Belső szerverhiba."
    }), 500


# ============================================================
# INDÍTÁS
# ============================================================

if __name__ == "__main__":
    port = int(
        os.environ.get(
            "PORT",
            8080
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )
