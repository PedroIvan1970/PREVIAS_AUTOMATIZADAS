from flask import Flask, jsonify
import json
import subprocess

app = Flask(__name__)

# ✅ Ejecuta el script UNA SOLA VEZ al iniciar el servidor
subprocess.run(["python", "consulta_api_ligmx_COMPLETO.py"], check=True)

@app.route("/ligamx/notas")
def obtener_notas():
    try:
        with open("notas_ligamx.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)})

