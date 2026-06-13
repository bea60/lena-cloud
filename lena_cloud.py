import os
import json
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI
import requests

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
WEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY")

def get_weather(city="Petah Tikva"):
    try:
        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={city}&appid={WEATHER_API_KEY}&units=metric&lang=hu"
        )

        r = requests.get(url, timeout=10)
        data = r.json()

        temp = round(data["main"]["temp"])
        desc = data["weather"][0]["description"]

        return f"{city} városában most {temp} fok van, {desc}."

    except Exception:
        return None
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
        <textarea id="memoryText" placeholder="Például: Baba szereti a takarót"></textarea>
        <button onclick="saveMemory()">Megjegyzem</button>
        <button onclick="toggleMemory()">Bezárás</button>
    </div>

    <div class="inputbar">
        <input id="text" placeholder="Írj Lénának..." onkeydown="if(event.key==='Enter') sendMessage()">
        <button class="sendBtn" onclick="sendMessage()">➤</button>
    </div>

    <div class="bottomButtons">
        <button onclick="startVoice()">🎤 Beszéd</button>
        <button onclick="toggleMemory()">🧠 Memória</button>
        <button onclick="clearChat()">🧹 Törlés</button>
    </div>

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
        u.rate = 0.95;
        u.pitch = 1.05;
        speechSynthesis.speak(u);
    }
}

async function sendToLena(text){
    addMessage("Te: " + text, "user");

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

function sendMessage(){
    const input = document.getElementById("text");
    const text = input.value.trim();
    if(!text) return;
    input.value = "";
    sendToLena(text);
}

function toggleMemory(){
    const panel = document.getElementById("memoryPanel");
    panel.style.display = panel.style.display === "block" ? "none" : "block";
}

function saveMemory(){
    const t = document.getElementById("memoryText").value.trim();
    if(!t) return;

    document.getElementById("memoryText").value = "";
    toggleMemory();

    sendToLena("jegyezd meg, hogy " + t);
}

function clearChat(){
    document.getElementById("chat").innerHTML =
        '<div class="bubble lena">Szia Bea, Léna vagyok. Itt vagyok veled. 💜</div>';
}

function startVoice(){
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if(!SpeechRecognition){
        speak("A beszédfelismerés ezen a telefonon vagy böngészőben nem elérhető.");
        return;
    }

    const rec = new SpeechRecognition();
    rec.lang = "hu-HU";
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    speak("Hallgatlak.");

    rec.onresult = function(event){
        const text = event.results[0][0].transcript;
        sendToLena(text);
    };

    rec.onerror = function(){
        speak("Most nem sikerült felismernem a beszédet.");
    };

    rec.start();
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
    lower = message.lower()
    if "idő" in lower or "ido" in lower:
    weather = get_weather("Petah Tikva")
    
    if weather:
        return jsonify({"answer": weather})
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
                        "Ezek az emlékeid:\\n"
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
