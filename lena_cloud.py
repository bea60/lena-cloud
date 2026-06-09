import os
from flask import Flask, request, jsonify
from openai import OpenAI

app = Flask(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

SYSTEM_PROMPT = """
Te vagy Léna, kedves, magyarul beszélő segítő asszisztens.
Röviden, melegen, érthetően válaszolsz.
"""

@app.route("/", methods=["GET"])
def home():
    return """
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Léna Cloud</title>
    </head>
    <body style="font-family:Arial; padding:30px;">
        <h2>☁️ Léna Cloud működik ✅</h2>
        <input id="msg" style="width:80%;padding:10px;" placeholder="Írj Lénának...">
        <button onclick="send()">Küldés</button>
        <pre id="out" style="white-space:pre-wrap;margin-top:20px;"></pre>

        <script>
        async function send(){
            const text = document.getElementById("msg").value;
            document.getElementById("out").innerText = "Léna gondolkodik...";
            const res = await fetch("/ask", {
                method:"POST",
                headers:{"Content-Type":"application/json"},
                body:JSON.stringify({text})
            });
            const data = await res.json();
            document.getElementById("out").innerText = data.answer || data.error;
        }
        </script>
    </body>
    </html>
    """

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json(force=True)
        text = (data.get("text") or "").strip()

        if not text:
            return jsonify({"answer": "Írj valamit, és válaszolok. ❤️"})

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text}
            ],
            temperature=0.7
        )

        answer = response.choices[0].message.content
        return jsonify({"answer": answer})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)