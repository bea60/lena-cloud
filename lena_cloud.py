import os
import json
import re
from datetime import datetime

import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI


app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MEMORY_FILE = "memory.json"
CHAT_FILE = "chat_history.json"
MOOD_FILE = "mood.json"


# ============================================================
# FÁJL SEGÉDFÜGGVÉNYEK
# ============================================================

def load_json(filename, default):
    try:
        if not os.path.exists(filename):
            return default

        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# HOSSZÚ TÁVÚ MEMÓRIA
# ============================================================

def load_memory():
    data = load_json(MEMORY_FILE, [])

    if isinstance(data, list):
        return data

    return []


def save_memory(memories):
    save_json(MEMORY_FILE, memories)


def memory_text():
    memories = load_memory()

    if not memories:
        return "Nincs még elmentett hosszú távú emlék."

    return "\n".join(
        f"- {item.get('text', '')}"
        for item in memories
        if item.get("text")
    )


def add_memory(text):
    text = text.strip()

    if not text:
        return False

    memories = load_memory()

    normalized = text.lower().strip()

    for item in memories:
        old = item.get("text", "").lower().strip()

        if old == normalized:
            return False

    memories.append(
        {
            "text": text,
            "created_at": datetime.now().isoformat()
        }
    )

    save_memory(memories)

    return True


def forget_memory(target):
    target = target.lower().strip()

    if not target:
        return False

    memories = load_memory()
    new_memories = []

    removed = False

    for item in memories:
        text = item.get("text", "")

        if target in text.lower():
            removed = True
        else:
            new_memories.append(item)

    if removed:
        save_memory(new_memories)

    return removed


# ============================================================
# BESZÉLGETÉSI ELŐZMÉNY
# ============================================================

def load_chat():
    data = load_json(CHAT_FILE, [])

    if isinstance(data, list):
        return data

    return []


def remember_chat(role, content):
    history = load_chat()

    history.append(
        {
            "role": role,
            "content": content
        }
    )

    # Ne nőjön végtelenre a fájl
    history = history[-100:]

    save_json(CHAT_FILE, history)


# ============================================================
# HANGULATNAPLÓ
# ============================================================

def recent_mood_text():
    moods = load_json(MOOD_FILE, [])

    if not isinstance(moods, list) or not moods:
        return "Nincs friss hangulati bejegyzés."

    recent = moods[-5:]

    lines = []

    for item in recent:
        if isinstance(item, dict):
            text = item.get("text", "")

            if text:
                lines.append(f"- {text}")

    if not lines:
        return "Nincs friss hangulati bejegyzés."

    return "\n".join(lines)


# ============================================================
# KIFEJEZETT MEMÓRIA KÉRÉS
# ============================================================

def extract_memory_request(message):
    text = message.strip()

    patterns = [
        r"(?i)^jegyezd meg(?:, hogy)?\s+(.+)$",
        r"(?i)^jegyezd meg ezt(?:, hogy)?\s+(.+)$",
        r"(?i)^emlékezz rá(?:, hogy)?\s+(.+)$",
        r"(?i)^emlékezz arra(?:, hogy)?\s+(.+)$",
        r"(?i)^tedd el(?:, hogy)?\s+(.+)$",
        r"(?i)^mentsd el(?:, hogy)?\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text)

        if match:
            return match.group(1).strip()

    return None


def extract_forget_request(message):
    text = message.strip()

    patterns = [
        r"(?i)^felejtsd el(?:, hogy)?\s+(.+)$",
        r"(?i)^felejtsd el ezt(?:, hogy)?\s+(.+)$",
        r"(?i)^töröld az emléket(?:, hogy)?\s+(.+)$",
        r"(?i)^töröld a memóriából(?:, hogy)?\s+(.+)$",
    ]

    for pattern in patterns:
        match = re.match(pattern, text)

        if match:
            return match.group(1).strip()

    return None


# ============================================================
# AUTOMATIKUS MEMÓRIA
# ============================================================

def auto_memory_candidate(message):
    text = message.strip()

    lower = text.lower()

    triggers = [
        "szeretem ",
        "nem szeretem ",
        "a kedvencem ",
        "azt szeretem",
        "azt nem szeretem",
        "mindig ",
        "soha ",
        "általában ",
    ]

    if any(trigger in lower for trigger in triggers):
        if 5 <= len(text) <= 300:
            return text

    return None


# ============================================================
# IDŐJÁRÁS
# ============================================================

def is_weather_question(message):
    text = message.lower()

    words = [
        "időjárás",
        "idő van",
        "hány fok",
        "hőmérséklet",
        "esik",
        "eső",
        "meleg van",
        "hideg van",
    ]

    return any(word in text for word in words)


def extract_city_with_ai(message):
    """
    Egyszerű alapértelmezés.
    Ha nem tudjuk biztosan a várost, Petah Tikvát használjuk.
    """

    text = message.lower()

    known_cities = {
        "petah tikva": "Petah Tikva",
        "petah tikván": "Petah Tikva",
        "petah tikva-ban": "Petah Tikva",
        "tel aviv": "Tel Aviv",
        "budapest": "Budapest",
        "jeruzsálem": "Jerusalem",
        "jerusalem": "Jerusalem",
        "haifa": "Haifa",
    }

    for key, value in known_cities.items():
        if key in text:
            return value

    return "Petah Tikva"


def get_weather(city):
    try:
        url = "https://wttr.in/" + requests.utils.quote(city)

        response = requests.get(
            url,
            params={
                "format": "j1"
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        current = data["current_condition"][0]

        temp = current.get("temp_C", "?")
        feels = current.get("FeelsLikeC", "?")
        humidity = current.get("humidity", "?")

        description = ""

        desc_list = current.get("weatherDesc", [])

        if desc_list:
            description = desc_list[0].get("value", "")

        answer = (
            f"{city} városában most {temp} °C van, "
            f"hőérzet szerint {feels} °C. "
            f"A páratartalom {humidity}%."
        )

        if description:
            answer += f" Az időjárás: {description}."

        return answer

    except Exception as e:
        print("WEATHER ERROR:", e)

        return (
            "Most nem sikerült lekérnem az időjárást. "
            "Próbáld meg egy kicsit később. 💜"
        )


# ============================================================
# OPENAI
# ============================================================

def ask_openai(system_prompt, history, message):
    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    for item in history:
        role = item.get("role")
        content = item.get("content")

        if role in ["user", "assistant"] and content:
            messages.append(
                {
                    "role": role,
                    "content": content
                }
            )

    messages.append(
        {
            "role": "user",
            "content": message
        }
    )

    response = client.chat.completions.create(
        model=os.environ.get(
            "OPENAI_MODEL",
            "gpt-4o-mini"
        ),
        messages=messages,
        temperature=0.7
    )

    return response.choices[0].message.content.strip()


# ============================================================
# FŐ CHAT VÉGPONT
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(silent=True) or {}

        message = str(
            data.get("message", "")
        ).strip()

        if not message:
            return jsonify(
                {
                    "answer": "Nem kaptam üzenetet."
                }
            ), 400

        print("USER:", message)

        remember_chat(
            "user",
            message
        )

        # ----------------------------------------------------
        # FELEJTÉS
        # ----------------------------------------------------

        forget = extract_forget_request(message)

        if forget:
            removed = forget_memory(forget)

            if removed:
                answer = "Elfelejtettem. 💜"
            else:
                answer = "Nem találtam ilyen emléket."

            remember_chat(
                "assistant",
                answer
            )

            return jsonify(
                {
                    "answer": answer
                }
            )

        # ----------------------------------------------------
        # KIFEJEZETT MEGJEGYZÉS
        # ----------------------------------------------------

        fact = extract_memory_request(message)

        if fact:
            added = add_memory(fact)

            if added:
                answer = "Megjegyeztem. 💜"
            else:
                answer = "Ezt már tudtam. 💜"

            remember_chat(
                "assistant",
                answer
            )

            return jsonify(
                {
                    "answer": answer
                }
            )

        # ----------------------------------------------------
        # IDŐJÁRÁS
        # ----------------------------------------------------

        if is_weather_question(message):
            city = extract_city_with_ai(message)

            answer = get_weather(city)

            remember_chat(
                "assistant",
                answer
            )

            return jsonify(
                {
                    "answer": answer
                }
            )

        # ----------------------------------------------------
        # AUTOMATIKUS MEMÓRIA
        # ----------------------------------------------------

        auto_fact = auto_memory_candidate(message)

        if auto_fact:
            add_memory(auto_fact)

        # ----------------------------------------------------
        # OPENAI BESZÉLGETÉS
        # ----------------------------------------------------

        memories = memory_text()

        # Az aktuális user üzenetet már elmentettük,
        # ezért azt kivesszük a history végéről.
        history = load_chat()[:-1][-12:]

        system_prompt = (
            "Te Léna vagy, Bea személyes magyar AI asszisztense. "
            "Mindig magyarul válaszolj, természetesen, kedvesen és tömören. "
            "Használd a rendelkezésre álló emlékeket, "
            "de ne találj ki személyes tényeket. "
            "Ha valami bizonytalan vagy ellentmondásos, kérdezz vissza. "
            "Ne mondd azt, hogy emlékszel valamire, ha nincs az emlékek "
            "vagy a beszélgetés között. "
            "A felhasználó kifejezett 'jegyezd meg' kéréseit "
            "a rendszer külön elmenti. "
            "Ha a kérdés a mai napra vagy a közelmúltra utal, "
            "a beszélgetési előzményeket is vedd figyelembe.\n\n"
            "HOSSZÚ TÁVÚ EMLÉKEK:\n"
            + memories
            + "\n\n"
            + "HANGULATNAPLÓ:\n"
            + recent_mood_text()
        )

        answer = ask_openai(
            system_prompt,
            history,
            message
        )

        remember_chat(
            "assistant",
            answer
        )

        print("LENA:", answer)

        return jsonify(
            {
                "answer": answer
            }
        )

    except Exception as e:
        print("CHAT ERROR:", repr(e))

        return jsonify(
            {
                "answer": "Szerverhiba történt. 💜",
                "error": str(e)
            }
        ), 500


# ============================================================
# TESZT VÉGPONT
# ============================================================

@app.route("/", methods=["GET"])
def home():
    return jsonify(
        {
            "status": "ok",
            "name": "Léna",
            "message": "Léna szervere működik. 💜"
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok"
        }
    )


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
