import os
import json
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MEMORY_FILE = "memory.json"

DEFAULT_MEMORIES = [
    "A felhasználó Bea.",
    "Ági Bea párja.",
    "Bea építi a telefonos Léna projektet.",
    "Léna telefonon fut Android appban.",
    "Baba, másik nevén Yoda, egy sphynx cica.",
    "Bea azt szereti, ha teljes, egyben cserélhető kódot kap, nem apró kutyulást.",
    "Léna magyarul, kedvesen, röviden válaszol."
]


def load_memory():
    memory = {"memories": DEFAULT_MEMORIES.copy()}

    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for item in saved.get("memories", []):
                    if item not in memory["memories"]:
                        memory["memories"].append(item)
        except Exception:
            pass

    return memory


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def add_memory(text):
    memory = load_memory()
    memories = memory.get("memories", [])

    if text and text not in memories:
        memories.append(text)

    memory["memories"] = memories[-80:]
    save_memory(memory)


def memory_text():
    memory = load_memory()
    memories = memory.get("memories", [])

    if not memories:
        return "Még nincs elmentett hosszú távú emlék."

    return "\n".join([f"- {m}" for m in memories])


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
            fact = fact.strip(".! ")
            return fact

    return None


HTML = """
<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Léna</title>

<style>
* {
    box-sizing: border-box;
}

body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: linear-gradient(#fff7ff, #f5ecff);
    color: #241628;
}

.app {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

.topbar {
    height: 86px;
    background: #231417;
    color: white;
    display: flex;
    align-items: center;
    padding-left: 28px;
    font-size: 26px;
    font-weight: bold;
}

.hero {
    position: relative;
    background: radial-gradient(circle at top, #5d1572, #22002f 70%);
    color: white;
    text-align: center;
    padding: 70px 20px 28px;
    border-bottom-left-radius: 34px;
    border-bottom-right-radius: 34px;
    overflow: visible;
}

.avatar-big {
    position: absolute;
    top: -38px;
    left: 50%;
    transform: translateX(-50%);
    width: 88px;
    height: 88px;
    border-radius: 50%;
    background: #efd0ff;
    border: 8px solid #c66cff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 42px;
    box-shadow: 0 0 25px #d56cff;
}

.hero-title {
    font-size: 44px;
    font-weight: bold;
}

.hero-sub {
    font-size: 21px;
    opacity: 0.95;
}

.today {
    align-self: center;
    margin: 34px 0 18px;
    background: #ead8ff;
    color: #5c2678;
    padding: 15px 34px;
    border-radius: 28px;
    font-size: 20px;
    font-weight: bold;
}

.chat {
    flex: 1;
    padding: 0 26px 120px;
    overflow-y: auto;
}

.row {
    display: flex;
    align-items: flex-end;
    gap: 12px;
    margin: 14px 0;
}

.row.user {
    justify-content: flex-end;
}

.mini-avatar {
    width: 46px;
    height: 46px;
    border-radius: 50%;
    background: #e9c3ff;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
}

.bubble {
    max-width: 78%;
    background: white;
    padding: 20px 24px;
    border-radius: 28px;
    font-size: 22px;
    line-height: 1.35;
    box-shadow: 0 8px 24px rgba(80, 30, 100, 0.08);
    white-space: pre-wrap;
}

.row.user .bubble {
    background: #e7dcff;
}

.inputbar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 14px 20px 22px;
    display: flex;
    gap: 12px;
    align-items: center;
    box-shadow: 0 -8px 22px rgba(80, 30, 100, 0.08);
}

.round-btn {
    width: 62px;
    height: 62px;
    border-radius: 50%;
    border: 0;
    background: #f
