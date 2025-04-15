from flask import Flask, jsonify
import subprocess
import json

app = Flask(__name__)

@app.route("/ligamx/notas")
def obtener_notas():
    # Ejecuta el script completo (asegúrate que este nombre sea correcto en tu repo)
    subprocess.run(["python", "consulta_api_ligmx_COMPLETO.py"], check=True)

    # Lee el JSON generado
    with open("notas_ligamx.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)
