import os
import json
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MEMORY_FILE = "memory.json"

DEFAULT_MEMORIES = [
    "Ági és Bea használják ezt az appot.",
    "Bea gyakran használja Lénát.",
    "Ági Izraelben, Petah Tikvában él.",
    "Bea Ági párja.",
    "Baba, másik nevén Yoda, a sphynx cica.",
    "Ha valaki azt írja, hogy Bea vagyok, akkor ő Bea.",
    "Ha valaki azt írja, hogy Ági vagyok, akkor ő Ági.",
]


def load_memory():
    memory = {"memories": DEFAULT_MEMORIES.copy()}

    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                saved_memories = saved.get("memories", [])
                for item in saved_memories:
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

    memory["memories"] = memories[-100:]
    save_memory(memory)


def memory_text():
    memory = load_memory()
    memories = memory.get("memories", [])
    return "\n".join([f"- {m}" for m in memories])


def extract_memory_request(message):
    triggers = [
       
