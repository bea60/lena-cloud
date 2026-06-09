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
<title>Léna Cloud</title>
</head>
<body style="font-family:Arial; margin:0; background:#f7f4ff;">
<div style="max-width:760px; margin:auto; min-height:100vh; display:flex; flex-direction:column;">
    <div style="background:#6b4eff; color:white; padding:18px; text-align:center; font-size:24px; font-weight:bold;">
        ☁️ Léna Cloud
    </div>

    <div style="text-align:center; padding:20px;">
        <div style="width:110px; height:110px; border-radius:50%; background:#6b4eff; color:white; display:flex; align-items:center; justify-content:center; font-size:52px; margin:auto;">
            👩‍💻
        </div>
        <div style="color:#666; margin-top:8px;">Felhős Léna asszisztens</div>
    </div>

    <div id="chat" style="flex:1; padding:15px;">
        <div style="background:#f3e8ff; padding:12px 15px; border-radius:18px; max-width:80%; margin:10px 0;">
            Szia Bea ❤️ Itt vagyok a felhőből.
        </div>
    </div>

    <div style="display:flex; gap:8px; padding:12px; background:white; border-top:1px solid #ddd;">
        <button onclick="startMic()" style="padding:14px; border:0; border-radius:12px; background:#ff4e8a; color:white; font-weight:bold;">🎤</button>
        <input id="text" placeholder="Írj vagy mondj valamit..." style="flex:1; padding:14px; font-size:16px; border-radius:12px; border:1px solid #bbb;" onkeydown="if(event.key==='Enter') sendMessage()">
        <button id="send" onclick="sendMessage()" style="padding:14px 18px; border:0; border-radius:12px; background:#6b4eff; color:white; font-weight:bold;">Küldés</button>
    </div>
</div>

<script>
let recognition = null;

function addMessage(text, who){
    const chat = document.getElementById("chat");
    const align = who === "user" ? "margin-left:auto;background:#dbeafe;" : "margin-right:auto;background:#f3e8ff;";
    const div = document.createElement("div");
    div.style.cssText = "padding:12px 15px;border-radius:18px;max-width:80%;margin:10px 0;white-space:pre-wrap;" + align;
    div.innerText = text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
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
        document.getElementById("text").placeholder = "Írj vagy mondj valamit...";
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
    data = request.get_json(force=True)
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"answer": "Írj vagy mondj valamit, és válaszolok. ❤️"})

    fact = extract_memory_request(message)

    if fact:
        add_memory(fact)
        return jsonify({"answer": f"Rendben ❤️ Elmentettem: {fact}"})

    memories = memory_text()

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": f"""
Te Léna vagy, kedves, magyar nyelvű AI asszisztens.
Röviden, melegen és érthetően válaszolj.

Léna hosszú távú memóriája:
{memories}

Ha a felhasználó azt kérdezi, mit tudsz róla, akkor a fenti memóriából válaszolj.
"""
            },
            {
                "role": "user",
                "content": message
            }
        ]
    )

    answer = response.choices[0].message.content
    return jsonify({"answer": answer})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
