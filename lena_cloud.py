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
    "Bea azt szereti, ha teljes, egyben cserélhető kódot kap.",
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
    memories = load_memory().get("memories", [])
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
body {
    margin: 0;
    font-family: Arial, sans-serif;
    background: #f7efff;
    color: #241628;
}

.topbar {
    background: #231417;
    color: white;
    padding: 24px;
    font-size: 28px;
    font-weight: bold;
}

.hero {
    background: #3b0754;
    color: white;
    text-align: center;
    padding: 34px 20px;
    border-bottom-left-radius: 30px;
    border-bottom-right-radius: 30px;
}

.hero-title {
    font-size: 42px;
    font-weight: bold;
}

.hero-sub {
    font-size: 20px;
}

#chat {
    padding: 20px;
    padding-bottom: 110px;
    overflow-y: auto;
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
    margin-left: 40px;
}

.lena {
    margin-right: 40px;
}

.inputbar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: white;
    padding: 14px;
    display: flex;
    gap: 10px;
    box-shadow: 0 -8px 22px rgba(80, 30, 100, 0.08);
}

#text {
    flex: 1;
    border: 1px solid #ddd;
    border-radius: 26px;
    padding: 16px;
    font-size: 20px;
}

button {
    border: 0;
    border-radius: 26px;
    padding: 14px 18px;
    background: #7b22ff;
    color: white;
    font-size: 22px;
}
</style>
</head>

<body>

<div class="topbar">Léna</div>

<div class="hero">
    <div class="hero-title">Léna 💜</div>
    <div class="hero-sub">A te személyes AI asszisztensed</div>
</div>

<div id="chat">
    <div class="bubble lena">Szia Bea, Léna vagyok. Itt vagyok veled. 💜</div>
</div>

<div class="inputbar">
    <input id="text" placeholder="Írj Lénának..." onkeydown="if(event.key==='Enter') sendMessage()">
    <button onclick="sendMessage()">➤</button>
</div>

<script>
function addMessage(text, who){
    const chat = document.getElementById("chat");
    const div = document.createElement("div");
    div.className = "bubble " + who;
    div.innerText = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function speak(text){
    console.log("SPEAK:", text);

    if (window.AndroidSpeech) {
        window.AndroidSpeech.speak(text);
        return;
    }

    if (window.speechSynthesis) {
        speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(text);
        u.lang = "hu-HU";
        speechSynthesis.speak(u);
    }
}

async function sendMessage(){
    const input = document.getElementById("text");
    const text = input.value.trim();
    if(!text) return;

    addMessage("Te: " + text, "user");
    input.value = "";

    const thinking = addMessage("Léna: Gondolkodom...", "lena");

    try{
        const res = await fetch("/ask", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({message: text})
        });

        const data = await res.json();
        const answer = data.answer || "Nem kaptam választ.";
        thinking.innerText = "Léna: " + answer;
        speak(answer);

    }catch(e){
        thinking.innerText = "Léna: Hiba történt.";
        speak("Hiba történt.");
    }
}
</script>

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
                        "Te Léna vagy, egy kedves magyar AI asszisztens. "
                        "Mindig magyarul válaszolj. "
                        "Röviden, természetesen, melegen válaszolj. "
                        "Ezek az emlékeid:\n"
                        + memories
                    )
                },
                {"role": "user", "content": message}
            ]
        )

        return jsonify({"answer": response.choices[0].message.content})

    except Exception as e:
        print("HIBA:", e)
        return jsonify({"answer": "Most nem sikerült válaszolnom. Nézd meg a Railway logot."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
