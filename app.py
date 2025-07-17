import streamlit as st
import requests
import datetime
import time
import json
from urllib.parse import urlencode
import math
import pandas as pd

# Konstanty pro API
PROKERALA_CLIENT_ID = "a299b037-8f17-4973-94ec-2ff6181170c9"
PROKERALA_CLIENT_SECRET = "uDo6680pyltTVtUI5Wu9q16sHUoeScGTsz5UunYr"
API_BASE_URL = "https://api.prokerala.com/v2/astrology"

# Geolokační data pro města
geolokace = {
    "Praha": {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
    "Přerov": {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"}
    # ... další města dle potřeby ...
}


def get_access_token():
    url = "https://api.prokerala.com/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": PROKERALA_CLIENT_ID,
        "client_secret": PROKERALA_CLIENT_SECRET,
    }
    try:
        resp = requests.post(url, data=data, timeout=30)
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        st.error(f"Chyba získání tokenu: {e}")
        return None


def call_prokerala_api(endpoint, params):
    token = get_access_token()
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE_URL}{endpoint}?{urlencode(params)}"
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.json().get("data")
    except Exception as e:
        st.error(f"Chyba API: {e}")
        return None


def validate_datetime(date_str, time_str):
    try:
        datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return True
    except ValueError:
        return False


def format_datetime_for_api(date_str, time_str):
    try:
        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+01:00"
    except ValueError:
        return None


def create_planet_table(planets):
    st.subheader("📋 Tabulka planet")
    # Podpora dict nebo list
    if isinstance(planets, dict) and "planet_position" in planets:
        planet_list = planets["planet_position"]
    elif isinstance(planets, list):
        planet_list = planets
    else:
        st.error("Neočekávaná struktura dat planet.")
        return
    symbols = {
        "Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
        "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
        "Ascendant":"ASC","Rahu":"☊","Ketu":"☋"
    }
    zodiac = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
              "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    ayanamsa = 23.9
    rows = []
    for p in planet_list:
        lon = (p.get("longitude", 0) + ayanamsa) % 360
        idx = int(lon // 30)
        sign = zodiac[idx]
        deg = lon % 30
        di = int(deg)
        mi = int((deg - di) * 60)
        rows.append({
            "Planet": f"{symbols.get(p['name'], p['name'])} {p['name']}",
            "Sign": sign,
            "Degree": f"{di}°{mi:02d}'",
            "House": p.get("position", "?"),
            "Motion": "Retrograde" if p.get("is_retrograde", False) else "Direct"
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def create_svg_chart(planets):
    st.subheader("🔮 Astrologické kolo")
    # Podpora dict nebo list
    if isinstance(planets, dict) and "planet_position" in planets:
        planet_list = planets["planet_position"]
    elif isinstance(planets, list):
        planet_list = planets
    else:
        st.info("Žádné astronomické souřadnice k zobrazení.")
        return
    size = 400
    r = size * 0.45
    cx = cy = size / 2
    ay = 23.9
    symbols = {
        "Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
        "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
        "Ascendant":"A","Rahu":"☊","Ketu":"☋"
    }
    glyphs = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]
    svg = [f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg">']
    # Kruh
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="black" stroke-width="2" fill="none"/>')
    # Segmenty a glyphy
    for i in range(12):
        ang = math.radians(90 - i*30)
        x2 = cx + r * math.cos(ang)
        y2 = cy - r * math.sin(ang)
        svg.append(f'<line x1="{cx}" y1="{cy}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="black" stroke-width="1"/>')
        angg = math.radians(90 - (i*30 + 15))
        gx = cx + (r+20) * math.cos(angg)
        gy = cy - (r+20) * math.sin(angg)
        svg.append(f'<text x="{gx:.1f}" y="{gy:.1f}" font-size="16" text-anchor="middle" alignment-baseline="middle">{glyphs[i]}</text>')
    # Planety
    for p in planet_list:
        lon = (p.get("longitude", 0) + ay) % 360
        ang = math.radians(90 - lon)
        px = cx + r * 0.75 * math.cos(ang)
        py = cy - r * 0.75 * math.sin(ang)
        sym = symbols.get(p['name'], p['name'][0])
        svg.append(f'<text x="{px:.1f}" y="{py:.1f}" font-size="18" text-anchor="middle" alignment-baseline="middle">{sym}</text>')
    svg.append('</svg>')
    st.markdown(f"""<div style='display:flex;justify-content:center;'>{''.join(svg)}</div>""", unsafe_allow_html=True)


def display_horoscope_results(data):
    planets = data.get('/planet-position', [])
    create_planet_table(planets)
    create_svg_chart(planets)

# UI
st.set_page_config(page_title="Zářivá duše • Astrologický horoskop", layout="centered")
st.markdown("""
<h1 style='text-align:center;color:#33cfcf;'>Zářivá duše • Astrologický horoskop</h1>
<h3 style='text-align:center;color:#33cfcf;'>Vaše hvězdná mapa narození</h3>
""", unsafe_allow_html=True)
with st.form("astro_form"):
    datum = st.text_input("Datum narození (YYYY-MM-DD)", "1990-01-01")
    cas = st.text_input("Čas narození (HH:MM)", "12:00")
    mesto = st.selectbox("Město narození", list(geolokace.keys()))
    submit = st.form_submit_button("Vypočítat horoskop")

if submit:
    if not validate_datetime(datum, cas):
        st.error("Špatný formát data nebo času.")
        st.stop()
    poz = geolokace[mesto]
    dt = format_datetime_for_api(datum, cas)
    if not dt:
        st.error("Chyba při formátování.")
        st.stop()
    params = {
        "datetime": dt,
        "coordinates": f"{poz['latitude']},{poz['longitude']}",
        "ayanamsa": 1,
        "house_system": "placidus",
        "orb": "default",
        "timezone": poz['timezone']
    }
    all_data = {}
    for ep in ["/planet-position","/birth-details","/kundli"]:
        d = call_prokerala_api(ep, params)
        if d:
            all_data[ep] = d
        time.sleep(1)
    if all_data.get('/planet-position'):
        display_horoscope_results(all_data)
    else:
        st.error("Nepodařilo se získat astrologická data.")

st.markdown('<div style="text-align:center;font-size:0.9em;margin-top:2em;">Powered by <a href="https://developer.prokerala.com/" target="_blank">Prokerala Astrology API</a></div>', unsafe_allow_html=True)
