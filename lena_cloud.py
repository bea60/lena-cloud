    background: #f0dcff;
    font-size: 30px;
}

#text {
    flex: 1;
    border: 1px solid #eee;
    border-radius: 30px;
    padding: 18px;
    font-size: 21px;
}

.send-btn {
    width: 62px;
    border-radius: 50%;
    border: 0;
    background: #7b22ff;
    color: white;
    font-size: 30px;
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
            <div class="bubble">Szia Bea, Léna vagyok. Itt vagyok veled. 💜</div>
        </div>
    </div>

    <div class="inputbar">
        <button class="round-btn">✨</button>
        <input id="text" placeholder="Írj Lénának..." onkeydown="if(event.key==='Enter') sendMessage()">
        <button class="send-btn" onclick="sendMessage()">➤</button>
    </div>
</div>

<script>
function addMessage(text, who){
    const chat = document.getElementById("chat");
    const div = document.createElement("div");
    div.className = "bubble";
    div.innerText = (who === "user" ? "Te: " : "Léna: ") + text;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
    return div;
}

function speak(text){
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

    addMessage(text, "user");
    input.value = "";

    const thinking = addMessage("Gondolkodom...", "lena");

    try{
        const res = await fetch("/ask", {
            method:"POST",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({message:text})
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
                        "Te Léna vagy. Magyarul, kedvesen és röviden válaszolsz. "
                        "Ezek az emlékeid:\n" + memories
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
