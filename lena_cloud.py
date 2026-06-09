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

.time {
    display: block;
    margin-top: 8px;
    color: #aaa;
    font-size: 16px;
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
    background: #f0dcff;
    font-size: 30px;
}

#text {
    flex: 1;
    min-width: 0;
    border: 1px solid #eee;
    border-radius: 30px;
    padding: 18px 22px;
    font-size: 21px;
    outline: none;
}

.send-btn {
    width: 62px;
    height: 62px;
    border-radius: 50%;
    border: 0;
    background: linear-gradient(135deg, #ba35ff, #7b22ff);
    color: white;
    font-size: 30px;
    flex-shrink: 0;
}
</style>
</head>

<body>
<div class="app">

    <div class="topbar">Léna</div>

    <div class="hero">
        <div class="avatar-big">👩🏻</div>
        <div class="hero-title">Léna 💜</div>
        <div class="hero-sub">A te személyes AI asszisztensed ✨</div>
    </div>

    <div class="today">Ma</div>

    <div id="chat" class="chat">
        <div class="row">
            <div class="mini-avatar">👩🏻</div>
            <div class="bubble">
                Szia, Léna vagyok. Kérdezz bármit, szívesen segítek! 💜
                <span class="time">most</span>
            </div>
        </div>
    </div>

    <div class="inputbar">
        <button class="round-btn" onclick="startMic()">✨</button>
        <input id="text" placeholder="Írj Lénának..." onkeydown="if(event.key==='Enter') sendMessage()">
        <button id="send" class="send-btn" onclick="sendMessage()">➤</button>
    </div>

</div>

<script>
let recognition = null;

function addMessage(text, who){
    const chat = document.getElementById("chat");
    const row = document.createElement("div");
    row.className = "row " + (who === "user" ? "user" : "");

    if(who !== "user"){
        const av = document.createElement("div");
        av.className = "mini-avatar";
        av.innerText = "👩🏻";
        row.appendChild(av);
    }

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerText = text;

    row.appendChild(bubble);
    chat.appendChild(row);
    chat.scrollTop = chat.scrollHeight;
    return bubble;
}

async function sendMessage(){
    const input = document.getElementById("text");
    const btn = document.getElementById("send");
    const text = input.value.trim();
    if(!text) return;

    addMessage(text, "user");
    input.value = "";
    btn.disabled = true;

    const thinking = addMessage("Léna gondolkodik...", "lena");

    try{
        const res = await fetch("/ask", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text})
        });

        const data = await res.json();
        const answer = data.answer || "Nem kaptam választ.";
        thinking.innerText = answer;
        speak(answer);
    }catch(e){
        thinking.innerText = "Hiba történt a válasz közben.";
    }

    btn.disabled = false;
}

function startMic(){
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if(!SpeechRecognition){
        alert("Ez a böngésző nem támogatja a beszédfelismerést. Chrome ajánlott.");
        return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = "hu-HU";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = function(){
        document.getElementById("text").placeholder = "Hallgatlak...";
    };

    recognition.onresult = function(event){
        const spoken = event.results[0][0].transcript;
        document.getElementById("text").value = spoken;
        sendMessage();
    };

    recognition.onerror = function(){
        alert("Nem sikerült felismerni a hangot.");
    };

    recognition.onend = function(){
        document.getElementById("text").placeholder = "Írj Lénának...";
    };

    recognition.start();
}

function speak(text){
    if(!window.speechSynthesis) return;

    speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "hu-HU";
    utterance.rate = 1;
    utterance.pitch = 1;

    speechSynthesis.speak(utterance);
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
                        "Te Léna vagy, egy kedves, magyar nyelvű személyes AI asszisztens. "
                        "Röviden, természetesen, melegen válaszolj. "
                        "Ezek a hosszú távú emlékek rólatok:\n"
                        + memories
                    )
                },
                {"role": "user", "content": message}
            ]
        )

        answer = response.choices[0].message.content
        return jsonify({"answer": answer})

    except Exception:
        return jsonify({"answer": "Most nem sikerült válaszolnom. Ellenőrizd az OpenAI API kulcsot vagy a Railway logot."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
