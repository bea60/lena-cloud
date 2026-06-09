import os
from flask import Flask, request, jsonify, render_template_string
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

HTML = """
<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Léna Cloud</title>
<style>
body{
    margin:0;
    font-family:Arial, sans-serif;
    background:linear-gradient(180deg,#f7f4ff,#ffffff);
}
.app{
    max-width:780px;
    margin:auto;
    min-height:100vh;
    display:flex;
    flex-direction:column;
}
.header{
    padding:18px;
    background:#6b4eff;
    color:white;
    font-size:24px;
    font-weight:bold;
    text-align:center;
}
.avatar{
    text-align:center;
    padding:18px;
}
.avatar img{
    width:120px;
    height:120px;
    border-radius:50%;
    object-fit:cover;
    box-shadow:0 4px 18px rgba(0,0,0,0.25);
}
.chat{
    flex:1;
    padding:15px;
    overflow-y:auto;
}
.msg{
    max-width:80%;
    padding:12px 15px;
    margin:10px 0;
    border-radius:18px;
    line-height:1.4;
    white-space:pre-wrap;
}
.user{
    background:#dbeafe;
    margin-left:auto;
}
.lena{
    background:#f3e8ff;
    margin-right:auto;
}
.inputbar{
    display:flex;
    gap:8px;
    padding:12px;
    background:white;
    border-top:1px solid #ddd;
    position:sticky;
    bottom:0;
}
input{
    flex:1;
    padding:14px;
    font-size:16px;
    border-radius:12px;
    border:1px solid #bbb;
}
button{
    padding:14px 18px;
    border:0;
    border-radius:12px;
    background:#6b4eff;
    color:white;
    font-weight:bold;
    cursor:pointer;
}
button:disabled{
    opacity:.6;
}
.small{
    font-size:13px;
    text-align:center;
    color:#666;
    padding-bottom:8px;
}
</style>
</head>
<body>
<div class="app">
    <div class="header">☁️ Léna Cloud működik ✅</div>

    <div class="avatar">
        <img src="https://i.imgur.com/9XnJQ8T.png" alt="Léna">
        <div class="small">Felhős Léna asszisztens</div>
    </div>

    <div id="chat" class="chat">
        <div class="msg lena">Szia Bea ❤️ Itt vagyok a felhőből.</div>
    </div>

    <div class="inputbar">
        <input id="text" placeholder="Írj Lénának..." onkeydown="if(event.key==='Enter') sendMessage()">
        <button id="send" onclick="sendMessage()">Küldés</button>
    </div>
</div>

<script>
async function sendMessage(){
    const input = document.getElementById("text");
    const btn = document.getElementById("send");
    const chat = document.getElementById("chat");
    const text = input.value.trim();

    if(!text) return;

    chat.innerHTML += `<div class="msg user">${escapeHtml(text)}</div>`;
    input.value = "";
    btn.disabled = true;

    const thinkingId = "thinking_" + Date.now();
    chat.innerHTML += `<div id="${thinkingId}" class="msg lena">Léna gondolkodik...</div>`;
    chat.scrollTop = chat.scrollHeight;

    try{
        const res = await fetch("/ask", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text})
        });

        const data = await res.json();
        document.getElementById(thinkingId).innerText = data.answer || "Nem kaptam választ.";
    }catch(e){
        document.getElementById(thinkingId).innerText = "Hiba történt a válasz közben.";
    }

    btn.disabled = false;
    chat.scrollTop = chat.scrollHeight;
}

function escapeHtml(text){
    return text.replace(/[&<>"']/g, function(m){
        return ({
            "&":"&amp;",
            "<":"&lt;",
            ">":"&gt;",
            '"':"&quot;",
            "'":"&#039;"
        })[m];
    });
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
        return jsonify({"answer": "Írj valamit, és válaszolok. ❤️"})

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {
                "role": "system",
                "content": "Te Léna vagy, kedves, magyar nyelvű AI asszisztens. Röviden, melegen és érthetően válaszolj."
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
