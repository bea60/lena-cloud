
import os
import json
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MEMORY_FILE = "memory.json"


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {"memories": []}
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"memories": []}


def save_memory(memory):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, ensure_ascii=False, indent=2)


def add_memory(text):
    memory = load_memory()
    memories = memory.get("memories", [])

    if text and text not in memories:
        memories.append(text)

    memory["memories"] = memories[-50:]
    save_memory(memory)


def memory_text():
    memory = load_memory()
    memories = memory.get("memories", [])

    if not memories:
        return "Még nincs elmentett hosszú távú emlék."

    return "\n".join([f"- {m}" for m in memories])
    
HTML = """
<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Léna</title>
<!-- Itt jön az összes HTML és script, amit eddig is írtál -->
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML)

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json() or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"answer": "Írj valamit, és válaszolok. 💜"})

    fact = extract_memory_request(message)
    if fact:
        add_memory(fact)
        return jsonify({"answer": "Megjegyeztem. 💜"})

    memories = memory_text()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Te Léna vagy, egy kedves, magyar nyelvű személyes AI asszisztens. "
                        "Röviden, természetesen, melegen válaszolj. "
                        "Ezek a hosszú távú emlékek rólatok:\n" + memories
                    )
                },
                {"role": "user", "content": message}
            ]
        )

        answer = response.choices[0].message.content
        return jsonify({"answer": answer})

    except Exception:
        return jsonify({"answer": "Most nem sikerült válaszolnom. Ellenőrizd az API kulcsot!"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

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

"PORT", 8080)))
   
 
