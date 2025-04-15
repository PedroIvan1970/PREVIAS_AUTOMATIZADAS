import os
import zipfile
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def descargar_chrome():
    url = "https://storage.googleapis.com/chrome-for-testing-public/121.0.6167.85/linux64/chrome-linux64.zip"
    ruta_destino = "/tmp/chrome"
    os.makedirs(ruta_destino, exist_ok=True)

    zip_path = os.path.join(ruta_destino, "chrome.zip")
    chrome_bin = os.path.join(ruta_destino, "chrome-linux64", "chrome")

    if not os.path.exists(chrome_bin):
        r = requests.get(url)
        with open(zip_path, "wb") as f:
            f.write(r.content)

        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(ruta_destino)

    return chrome_bin


# -----------------------
# 1. Scraping LIGA MX WEB
# -----------------------
chrome_path = descargar_chrome()

options = Options()
options.binary_location = chrome_path  # ✅ Aquí se usa el binario descargado
options.add_argument("--headless")  # 👈 obligatorio en Render
options.add_argument("--no-sandbox")  # 👈 recomendado para servidores Linux
options.add_argument("--disable-dev-shm-usage")  # 👈 mejora estabilidad

# 👇 esta línea descarga automáticamente el driver correcto
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=options)


driver.get("https://ligamx.net/cancha/marcadores")
time.sleep(7)

links = driver.find_elements(By.TAG_NAME, "a")
partidos_links = []

for link in links:
    href = link.get_attribute("href")
    if href and "informeArbitral" in href:
        hora_elem = link.find_element(By.CLASS_NAME, "hora") if link.find_elements(By.CLASS_NAME, "hora") else None
        fecha_elem = link.find_element(By.CLASS_NAME, "fecha") if link.find_elements(By.CLASS_NAME, "fecha") else None

        hora = hora_elem.text.strip() if hora_elem else "Hora no disponible"
        fecha = fecha_elem.text.strip() if fecha_elem else "Fecha no disponible"

        match = re.search(r'informeArbitral/(\d+)/([^/]+)/([^/]+)', href)
        if not match:
            continue

        slug = match.group(3)
        jornada_match = re.search(r'jornada-(\d+)', slug)
        jornada = jornada_match.group(1) if jornada_match else "?"

        estadio = slug.split("estadio-")[-1].replace("-", " ").title()
        equipos_txt = slug.replace("informe-arbitral-", "").split("-jornada-")[0]
        equipos_txt = equipos_txt.replace("-", " ").title()

        if " Vs " in equipos_txt:
            equipo_local, equipo_visitante = equipos_txt.split(" Vs ", 1)
        else:
            equipo_local, equipo_visitante = "", ""

        partidos_links.append({
            "Equipo Local": equipo_local.strip(),
            "Equipo Visitante": equipo_visitante.strip(),
            "Fecha (Web)": fecha,
            "Hora (Web)": hora,
            "Jornada": jornada,
            "Estadio Web": estadio
        })

driver.quit()

# -----------------------
# 2. Limpieza de datos del sitio
# -----------------------
def separar_estadio_canales(texto):
    partes = texto.strip().split()
    canales = []
    while partes and partes[-1].lower() in [
        'tudn', 'televisa', 'vix', 'espn', 'tv', 'azteca',
        'calientemx', 'amazon', 'prime', '7', 'nd', 'tubi'
    ]:
        canales.insert(0, partes.pop())
    estadio = ' '.join(partes)
    canales = ' '.join(canales)
    return estadio, canales

df_web = pd.DataFrame(partidos_links).drop_duplicates()
df_web[['Estadio', 'Canales']] = df_web['Estadio Web'].apply(lambda x: pd.Series(separar_estadio_canales(x)))
df_web.drop(columns='Estadio Web', inplace=True)

# -----------------------
# 3. Datos desde la API (solo para complementar)
# -----------------------
api_key = "3f8dc361c2msheb4d11513f30435p1a06d7jsn2c0e3280bd50"
url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
params = {"league": "262", "season": "2024", "status": "NS"}
headers = {
    "X-RapidAPI-Key": api_key,
    "X-RapidAPI-Host": "api-football-v1.p.rapidapi.com"
}

response = requests.get(url, headers=headers, params=params)
fixtures = []

if response.status_code == 200:
    for match in response.json()["response"]:
        fixture = match["fixture"]
        teams = match["teams"]
        fixtures.append({
            "Equipo Local API": teams["home"]["name"],
            "Equipo Visitante API": teams["away"]["name"],
            "Fecha UTC": fixture["date"],
            "Estadio API": fixture["venue"]["name"],
            "Ciudad": fixture["venue"]["city"]
        })

    df_api = pd.DataFrame(fixtures)
    df_api["Fecha UTC"] = pd.to_datetime(df_api["Fecha UTC"], utc=True)
    df_api["Fecha Local"] = df_api["Fecha UTC"].dt.tz_convert("America/Mexico_City")
    df_api["Fecha"] = df_api["Fecha Local"].dt.strftime("%A %d %B %Y")
    df_api["Hora"] = df_api["Fecha Local"].dt.strftime("%H:%M")
else:
    print("❌ Error:", response.status_code, response.text)
    df_api = pd.DataFrame()

# -----------------------
# 4. Normalización y alias
# -----------------------
def normalizar(nombre):
    nombre = nombre.lower().replace("f.c.", "").replace("fc", "")
    nombre = nombre.replace("club", "").replace("de futbol", "")
    nombre = nombre.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    nombre = re.sub(r'\s+', ' ', nombre).strip()
    return nombre

alias_equipos = {
    "universidad nacional": "u.n.a.m. - pumas",
    "atletico de san luis": "atletico san luis",
    "gallos blancos de queretaro": "queretaro",
    "mazatlan fc": "mazatlan",
    "fc juarez": "fc juarez",
    "tigres de la uanl": "tigres uanl",
    "puebla fc": "puebla",
    "cruz azul": "cruz azul",
    "leon": "leon",
    "monterrey": "monterrey",
    "america": "club america",
    "atlas": "atlas",
    "toluca": "toluca",
    "tijuana": "tijuana",
    "necaxa": "necaxa",
    "guadalajara": "guadalajara chivas",
    "pachuca": "pachuca",
    "santos laguna": "santos laguna"
}

# Normalizar y aplicar alias
for df in [df_web, df_api]:
    df["local_key"] = df["Equipo Local" if "Equipo Local" in df.columns else "Equipo Local API"].apply(lambda x: alias_equipos.get(normalizar(x), normalizar(x)))
    df["visitante_key"] = df["Equipo Visitante" if "Equipo Visitante" in df.columns else "Equipo Visitante API"].apply(lambda x: alias_equipos.get(normalizar(x), normalizar(x)))

# -----------------------
# 5. Unión tolerante (fuente oficial: Liga MX)
# -----------------------
# 1. MERGE NORMAL
df_1 = pd.merge(
    df_web,
    df_api,
    on=["local_key", "visitante_key"],
    how="left",
    suffixes=("", "_api")
)

# 2. MERGE INVERTIDO
df_web_inv = df_web.copy()
df_web_inv = df_web_inv.rename(columns={
    "local_key": "visitante_key",
    "visitante_key": "local_key"
})
df_2 = pd.merge(
    df_web_inv,
    df_api,
    on=["local_key", "visitante_key"],
    how="left",
    suffixes=("", "_api")
)

# Restaurar columnas del sitio oficial
df_2[["Equipo Local", "Equipo Visitante", "Jornada", "Estadio", "Canales"]] = df_web[["Equipo Local", "Equipo Visitante", "Jornada", "Estadio", "Canales"]]

# Combinar resultados, priorizando el primer merge
for col in ["Fecha", "Hora", "Ciudad"]:
    df_1[col] = df_1[col].combine_first(df_2[col])

df_final = df_1[[
    "Jornada", "Equipo Local", "Equipo Visitante", "Fecha", "Hora",
    "Estadio", "Ciudad", "Canales"
]].sort_values(by=["Jornada", "Fecha"], na_position="last")

# -----------------------
# 6. Mostrar tabla final
# -----------------------
pd.set_option('display.max_columns', None)
print(df_final.to_string(index=False))

# Diccionario con los IDs oficiales de los equipos
team_ids = {
    "guadalajara chivas": 2278,
    "tigres uanl": 2279,
    "club tijuana": 2280,
    "toluca": 2281,
    "monterrey": 2282,
    "atlas": 2283,
    "santos laguna": 2285,
    "u.n.a.m. - pumas": 2286,
    "club america": 2287,
    "necaxa": 2288,
    "leon": 2289,
    "queretaro": 2290,
    "puebla": 2291,
    "pachuca": 2292,
    "cruz azul": 2295,
    "fc juarez": 2298,
    "atletico san luis": 2314,
    "mazatlan": 14002
}

# Alias sin alterar la función normalizar()
alias_equipos = {
    "universidad nacional": "u.n.a.m. - pumas",
    "club atletico de san luis": "atletico san luis",
    "gallos blancos de queretaro": "queretaro",
    "mazatlan fc": "mazatlan",
    "fc juarez": "fc juarez",
    "tigres de la uanl": "tigres uanl",
    "puebla fc": "puebla",
    "cruz azul": "cruz azul",
    "leon": "leon",
    "monterrey": "monterrey",
    "america": "club america",
    "atlas": "atlas",
    "toluca": "toluca",
    "tijuana": "club tijuana",
    "necaxa": "necaxa",
    "guadalajara": "guadalajara chivas",
    "pachuca": "pachuca",
    "santos laguna": "santos laguna"
}

def obtener_historial(id_local, id_visitante):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures/headtohead"
    params = {"h2h": f"{id_local}-{id_visitante}"}
    r = requests.get(url, headers=headers, params=params)
    data = r.json().get("response", [])[:10]
    historial = []
    for p in data:
        l = p["teams"]["home"]["name"]
        v = p["teams"]["away"]["name"]
        g1 = p["goals"]["home"]
        g2 = p["goals"]["away"]
        historial.append(f"{p['fixture']['date'][:10]}: {l} {g1} - {g2} {v}")
    return historial

def obtener_ultimos_resultados(id_equipo):
    url = "https://api-football-v1.p.rapidapi.com/v3/fixtures"
    params = {
        "team": id_equipo,
        "league": "262",
        "season": "2024",
        "status": "FT"
    }
    r = requests.get(url, headers=headers, params=params)
    data = r.json().get("response", [])[:5]
    resultados = []
    for p in data:
        l = p["teams"]["home"]["name"]
        v = p["teams"]["away"]["name"]
        g1 = p["goals"]["home"]
        g2 = p["goals"]["away"]
        resultados.append(f"{p['fixture']['date'][:10]}: {l} {g1} - {g2} {v}")
    return resultados

# 🔁 Loop con identificación robusta usando alias
for _, row in df_final.iterrows():
    local = row["Equipo Local"].lower().strip()
    visitante = row["Equipo Visitante"].lower().strip()

    local_ajustado = alias_equipos.get(local, local)
    visitante_ajustado = alias_equipos.get(visitante, visitante)

    id_local = team_ids.get(local_ajustado)
    id_visitante = team_ids.get(visitante_ajustado)

    print(f"\n🔷 {row['Equipo Local']} vs {row['Equipo Visitante']}")
    if id_local and id_visitante:
        print("🟡 Últimos 10 enfrentamientos:")
        for linea in obtener_historial(id_local, id_visitante):
            print("  -", linea)

        print(f"🔵 Últimos 5 resultados de {row['Equipo Local']}:")
        for linea in obtener_ultimos_resultados(id_local):
            print("  -", linea)

        print(f"🔴 Últimos 5 resultados de {row['Equipo Visitante']}:")
        for linea in obtener_ultimos_resultados(id_visitante):
            print("  -", linea)
    else:
        print("⚠️ No se encontró el ID para uno de los equipos.")

import json

# Guardar resultados como estructura enriquecida
notas = []

for _, row in df_final.iterrows():
    local = row["Equipo Local"]
    visitante = row["Equipo Visitante"]
    # usa aquí los IDs como ya hicimos antes
    nombre_local = alias_equipos.get(local.lower().strip(), local.lower().strip())
    nombre_visitante = alias_equipos.get(visitante.lower().strip(), visitante.lower().strip())

    id_local = team_ids.get(nombre_local)
    id_visitante = team_ids.get(nombre_visitante)

    if id_local and id_visitante:
        historial = obtener_historial(id_local, id_visitante)
        ult_local = obtener_ultimos_resultados(id_local)
        ult_visitante = obtener_ultimos_resultados(id_visitante)

        notas.append({
            "jornada": row["Jornada"],
            "equipo_local": local,
            "equipo_visitante": visitante,
            "fecha": row["Fecha"],
            "hora": row["Hora"],
            "estadio": row["Estadio"],
            "ciudad": row["Ciudad"],
            "canales": row["Canales"],
            "headtohead": historial,
            "ultimos_local": ult_local,
            "ultimos_visitante": ult_visitante
        })

# Guardar en archivo JSON
with open("notas_ligamx.json", "w", encoding="utf-8") as f:
    json.dump(notas, f, ensure_ascii=False, indent=2)

