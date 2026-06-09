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
    "Baba egy sphynx macska.",
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
        "jegyezd meg",
        "emlékezz rá",
        "mentsd el",
        "tanuld meg",
        "ne felejtsd el",
        "fontos hogy",
        "fontos, hogy",
    ]

    lower = message.lower()

    for trigger in triggers:
        if trigger in lower:
            index = lower.find(trigger)
            remembered = message[index + len(trigger):].strip(" :,-.")
            if remembered:
                return remembered

    return None


@app.route("/")
def index():
    return render_template_string("""
<!DOCTYPE html>
<html lang="hu">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Léna</title>

    <style>
        body {
            margin: 0;
            font-family: Arial, sans-serif;
            background: #fff7f8;
            color: #2b1b1f;
        }

        .header {
            background: #2b171c;
            color: white;
            padding: 22px;
            font-size: 28px;
            font-weight: bold;
        }

        .chat {
            padding: 16px;
            padding-bottom: 120px;
        }

        .message {
            margin: 10px 0;
            padding: 12px 14px;
            border-radius: 16px;
            max-width: 85%;
            line-height: 1.4;
            white-space: pre-wrap;
        }

        .user {
            background: #d9ecff;
            margin-left: auto;
        }

        .lena {
            background: #ffffff;
            border: 1px solid #ead6dc;
            margin-right: auto;
        }

        .inputbar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #ffffff;
            border-top: 1px solid #ddd;
            display: flex;
            gap: 8px;
            padding: 12px;
        }

        input {
            flex: 1;
            font-size: 17px;
            padding: 12px;
            border-radius: 12px;
            border: 1px solid #ccc;
        }

        button {
            font-size: 17px;
            padding: 12px 16px;
            border-radius: 12px;
            border: none;
            background: #2b171c;
            color: white;
            font-weight: bold;
        }
    </style>
</head>

<body>
    <div class="header">Léna</div>

    <div id="chat" class="chat">
        <div class="message lena">Szia ❤️ Itt vagyok.</div>
    </div>

    <div class="inputbar">
        <input id="messageInput" type="text" placeholder="Írj Lénának..." />
        <button onclick="sendMessage()">Küldés</button>
    </div>

    <script>
        const chat = document.getElementById("chat");
        const input = document.getElementById("messageInput");

        function addMessage(text, who) {
            const div = document.createElement("div");
            div.className = "message " + who;
            div.textContent = text;
            chat.appendChild(div);
            window.scrollTo(0, document.body.scrollHeight);
        }

        async function sendMessage() {
            const text = input.value.trim();
            if (!text) return;

            addMessage(text, "user");
            input.value = "";

            addMessage("Gondolkodom...", "lena");

            try {
                const response = await fetch("/chat", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({ message: text })
                });

                const data = await response.json();

                const thinking = chat.lastChild;
                thinking.textContent = data.reply || "Nem kaptam választ.";
            } catch (err) {
                const thinking = chat.lastChild;
                thinking.textContent = "Hiba történt. Nem tudtam válaszolni.";
            }
        }

        input.addEventListener("keydown", function(event) {
            if (event.key === "Enter") {
                sendMessage();
            }
        });
    </script>
</body>
</html>
""")


@app.route("/chat", methods=["POST"])
def chat():
    try:
        data = request.get_json(force=True)
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({"reply": "Nem kaptam üzenetet."})

        memory_to_save = extract_memory_request(user_message)
        if memory_to_save:
            add_memory(memory_to_save)

        memories = memory_text()

        system_prompt = f"""
Te Léna vagy, Ági és Bea magyar nyelvű segítő asszisztense.

Mindig magyarul válaszolj.
Légy kedves, természetes, rövid és segítőkész.
Ha Bea írja, hogy „Bea vagyok”, akkor Beának beszélsz.
Ha Ági írja, hogy „Ági vagyok”, akkor Áginak beszélsz.

Fontos emlékek:
{memories}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=0.6,
        )

        reply = response.choices[0].message.content.strip()

        if not reply:
            reply = "Nem kaptam választ."

        return jsonify({"reply": reply})

    except Exception as e:
        print("HIBA:", str(e), flush=True)
        return jsonify({"reply": "Nem kaptam választ.", "error": str(e)}), 500


@app.route("/memory", methods=["GET"])
def memory():
    return jsonify(load_memory())


@app.route("/add_memory", methods=["POST"])
def add_memory_route():
    try:
        data = request.get_json(force=True)
        text = data.get("text", "").strip()

        if not text:
            return jsonify({"ok": False, "message": "Nincs mit elmenteni."})

        add_memory(text)
        return jsonify({"ok": True, "message": "Elmentve.", "memory": load_memory()})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
