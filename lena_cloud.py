import os, json
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
    text = text.strip()
    if text and text not in memory["memories"]:
        memory["memories"].append(text)
    memory["memories"] = memory["memories"][-80:]
    save_memory(memory)

def memory_text():
    return "\n".join("- " + m for m in load_memory().get("memories", []))

HTML = """
<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Léna</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;font-family:Arial,sans-serif}
body{
    background:linear-gradient(180deg,#fff7ff,#f7f0ff);
    color:#211425;
    padding-bottom:96px;
}
.header{
    height:205px;
    background:radial-gradient(circle at top,#5b2168,#2a0d39 65%,#1b0627);
    color:white;
    border-bottom-left-radius:30px;
    border-bottom-right-radius:30px;
    padding:14px 20px 18px;
    text-align:center;
    box-shadow:0 10px 28px rgba(88,34,110,.30);
}
.top{
    display:flex;
    justify-content:space-between;
    align-items:center;
    height:34px;
}
.menu{font-size:28px}
.memory{
    background:rgba(255,255,255,.14);
    padding:8px 12px;
    border-radius:22px;
    font-size:13px;
}
.dot{
    display:inline-block;
    width:9px;height:9px;
    background:#00e676;
    border-radius:50%;
    margin-left:6px;
}
.avatar{
    width:82px;height:82px;
    margin:4px auto 8px;
    border-radius:50%;
    background:linear-gradient(135deg,#ffd6ff,#a44cff);
    padding:5px;
    box-shadow:0 0 22px rgba(220,140,255,.75);
}
.avatar-inner{
    width:100%;height:100%;
    border-radius:50%;
    background:#ffe6f6;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:43px;
}
h1{
    margin:2px 0 2px;
    font-size:36px;
    line-height:1.05;
}
.subtitle{
    opacity:.92;
    font-size:16px;
}
.chat{
    padding:20px 18px 20px;
}
.day{
    margin:0 auto 18px;
    width:max-content;
    background:#ead8ff;
    color:#512171;
    padding:9px 24px;
    border-radius:22px;
    font-weight:bold;
}
.row{
    display:flex;
    margin:14px 0;
    gap:10px;
    align-items:flex-end;
}
.row.user{justify-content:flex-end}
.mini{
    width:38px;height:38px;
    border-radius:50%;
    background:#f3c7ff;
    display:flex;
    align-items:center;
    justify-content:center;
    font-size:23px;
    flex-shrink:0;
}
.bubble{
    max-width:78%;
    padding:16px 18px;
    border-radius:24px;
    font-size:18px;
    line-height:1.35;
    box-shadow:0 8px 22px rgba(50,0,80,.08);
}
.lena .bubble{
    background:white;
    border-bottom-left-radius:8px;
}
.user .bubble{
    background:linear-gradient(135deg,#efd3ff,#d8a9ff);
    color:#3b1165;
    border-bottom-right-radius:8px;
    font-weight:600;
}
.time{
    display:block;
    margin-top:8px;
    font-size:13px;
    opacity:.45;
}
.inputbar{
    position:fixed;
    bottom:0;left:0;right:0;
    padding:12px 12px 16px;
    background:rgba(255,255,255,.90);
    backdrop-filter:blur(12px);
    display:flex;
    gap:10px;
    align-items:center;
}
.spark{
    width:54px;height:54px;
    border:0;
    border-radius:50%;
    background:#f1e0ff;
    font-size:25px;
}
input{
    flex:1;
    height:54px;
    border:0;
    border-radius:22px;
    padding:0 18px;
    font-size:18px;
    outline:none;
    box-shadow:inset 0 0 0 1px #eee;
}
.send{
    width:60px;height:60px;
    border:0;
    border-radius:50%;
    background:linear-gradient(135deg,#b84dff,#7b20e8);
    color:white;
    font-size:28px;
    box-shadow:0 8px 24px rgba(123,32,232,.35);
}
</style>
</head>
<body>

<div class="header">
    <div class="top">
        <div class="menu">☰</div>
        <div class="memory">🧠 Memória aktív <span class="dot"></span></div>
    </div>
    <div class="avatar"><div class="avatar-inner">👩🏻</div></div>
    <h1>Léna 💜</h1>
    <div class="subtitle">A te személyes AI asszisztensed ✨</div>
</div>

<div class="chat" id="chat">
    <div class="day">Ma</div>
    <div class="row lena">
        <div class="mini">👩🏻</div>
        <div class="bubble">Szia, Léna vagyok. Kérdezz bármit, szívesen segítek! 💜<span class="time">most</span></div>
    </div>
</div>

<div class="inputbar">
    <button class="spark">✨</button>
    <input id="msg" placeholder="Írj Lénának..." onkeydown="if(event.key==='Enter')sendMsg()">
    <button class="send" onclick="sendMsg()">➤</button>
</div>

<script>
const chat=document.getElementById("chat");
const input=document.getElementById("msg");

function now(){
    const d=new Date();
    return d.getHours().toString().padStart(2,'0')+":"+d.getMinutes().toString().padStart(2,'0');
}

function safeText(text){
    return text.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
}

function add(text, who){
    const row=document.createElement("div");
    row.className="row "+who;
    const clean=safeText(text);
    if(who==="lena"){
        row.innerHTML='<div class="mini">👩🏻</div><div class="bubble">'+clean+'<span class="time">'+now()+'</span></div>';
    }else{
        row.innerHTML='<div class="bubble">'+clean+'<span class="time">'+now()+' ✓✓</span></div>';
    }
    chat.appendChild(row);
    window.scrollTo(0,document.body.scrollHeight);
}

async function sendMsg(){
    const text=input.value.trim();
    if(!text)return;
    input.value="";
    add(text,"user");

    add("Gondolkodom...","lena");
    const last=chat.lastChild.querySelector(".bubble");

    try{
        const res=await fetch("/chat",{
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text})
        });
        const data=await res.json();
        last.innerHTML=safeText(data.reply || "Nem kaptam választ.")+'<span class="time">'+now()+'</span>';
    }catch(e){
        last.innerHTML='Hiba történt. Próbáld újra. <span class="time">'+now()+'</span>';
    }
}
</script>

</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message", "").strip()
    low = user_message.lower()

    system_prompt = f"""
Te Léna vagy, magyarul beszélő, kedves személyes asszisztens.
Röviden, természetesen válaszolj.
Ne mondd mindig, hogy "miben segíthetek".
Ha a választ tudod a memóriából, válaszolj magabiztosan.

Memóriád:
{memory_text()}
"""

    memory_triggers = [
        "jegyezd meg",
        "emlékezz erre",
        "mentsd el",
        "tárold el",
        "ne felejtsd el"
    ]

    if any(low.startswith(t) for t in memory_triggers):
        cleaned = user_message
        for t in memory_triggers:
            cleaned = cleaned.replace(t, "", 1).replace(t.capitalize(), "", 1)
        cleaned = cleaned.strip(" :.!,-")
        add_memory(cleaned)
        return jsonify({"reply": "Megjegyeztem 💜"})

    try:
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ]
        )
        reply = response.choices[0].message.content
    except Exception:
        reply = "Most nem sikerült válaszolnom, de itt vagyok 💜"

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
