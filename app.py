import streamlit as st
import requests
import datetime
import time
import math
import json
from urllib.parse import urlencode
import pandas as pd
import traceback

# Konstanty
PROKERALA_CLIENT_ID = "a299b037-8f17-4973-94ec-2ff6181170c9"
PROKERALA_CLIENT_SECRET = "uDo6680pyltTVtUI5Wu9q16sHUoeScGTsz5UunYr"
API_BASE_URL = "https://api.prokerala.com/v2/astrology"

gelocations = {
    "Praha":  {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
    "Přerov": {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"}
}

element_colors = {
    "Aries": "#ffe6e6", "Leo": "#ffe6e6", "Sagittarius": "#ffe6e6",
    "Taurus": "#e6ffe6", "Virgo": "#e6ffe6", "Capricorn": "#e6ffe6",
    "Gemini": "#e6e6ff", "Libra": "#e6e6ff", "Aquarius": "#e6e6ff",
    "Cancer": "#e6ffff", "Scorpio": "#e6ffff", "Pisces": "#e6ffff"
}

planet_symbols = {
    "Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
    "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
    "Ascendant":"ASC","Rahu":"☊","Ketu":"☋"
}

zodiac = [
    "Aries","Taurus","Gemini","Cancer","Leo","Virgo",
    "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"
]
glyphs = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]

def get_access_token():
    try:
        resp = requests.post(
            "https://api.prokerala.com/token",
            data={
                "grant_type": "client_credentials",
                "client_id": PROKERALA_CLIENT_ID,
                "client_secret": PROKERALA_CLIENT_SECRET
            },
            timeout=30
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        st.error(f"Chyba tokenu: {e}")
        return None


def call_prokerala_api(endpoint, params):
    token = get_access_token()
    if not token:
        return None
    try:
        resp = requests.get(
            f"{API_BASE_URL}{endpoint}?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        resp.raise_for_status()
        return resp.json().get("data")
    except Exception as e:
        st.error(f"Chyba API: {e}")
        return None


def validate_datetime(date_str, time_str):
    try:
        datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return True
    except:
        return False


def format_datetime_for_api(date_str, time_str):
    try:
        dt = datetime.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+01:00"
    except:
        return None


def create_planet_table(planets):
    st.subheader("📋 Tabulka planet")
    if isinstance(planets, dict) and "planet_position" in planets:
        pl = planets["planet_position"]
    elif isinstance(planets, list):
        pl = planets
    else:
        st.error("Chyba struktury planet")
        return
    ay = 23.9
    rows = []
    for p in pl:
        lon = (p.get("longitude", 0) + ay) % 360
        idx = int(lon // 30)
        sign = zodiac[idx]
        deg = lon % 30
        di = int(deg)
        mi = int((deg - di) * 60)
        rows.append({
            "Planet": f"{planet_symbols.get(p['name'], p['name'])} {p['name']}",
            "Sign": sign,
            "Degree": f"{di}°{mi:02d}'",
            "House": p.get("position", "?"),
            "Motion": "Retrograde" if p.get("is_retrograde", False) else "Direct"
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def create_svg_chart(planets):
    st.subheader("🔮 Astrologické kolo")
    if isinstance(planets, dict) and "planet_position" in planets:
        pl = planets["planet_position"]
    elif isinstance(planets, list):
        pl = planets
    else:
        st.info("Žádná data k vizualizaci.")
        return
    size = 450
    cx = cy = size / 2
    r_outer = size * 0.45
    r_inner = r_outer * 0.9
    ay = 23.9
    svg = [
        f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg" '
        'style="background:#fff;border-radius:10px;box-shadow:0 2px 6px rgba(0,0,0,0.15)">'
    ]
    for i, sign in enumerate(zodiac):
        start_rad = math.radians(90 - i * 30)
        end_rad = math.radians(90 - (i + 1) * 30)
        x1, y1 = cx + r_outer * math.cos(start_rad), cy - r_outer * math.sin(start_rad)
        x2, y2 = cx + r_outer * math.cos(end_rad), cy - r_outer * math.sin(end_rad)
        col = element_colors.get(sign, "#f0f0f0")
        path = f"M{cx},{cy} L{x1:.1f},{y1:.1f} A{r_outer},{r_outer} 0 0,1 {x2:.1f},{y2:.1f} Z"
        svg.append(f'<path d="{path}" fill="{col}" stroke="none"/>')
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" stroke="#888" stroke-width="2" fill="none"/>')
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r_inner}" stroke="#ccc" stroke-width="1" fill="none"/>')
    for i, g in enumerate(glyphs):
        angle_rad = math.radians(90 - (i * 30 + 15))
        gx = cx + (r_outer + 20) * math.cos(angle_rad)
        gy = cy - (r_outer + 20) * math.sin(angle_rad)
        svg.append(f'<text x="{gx:.1f}" y="{gy:.1f}" font-size="18" text-anchor="middle" fill="#444" alignment-baseline="middle">{g}</text>')
    for p in pl:
        lon = (p.get("longitude", 0) + ay) % 360
        ang_rad = math.radians(90 - lon)
        px = cx + r_inner * math.cos(ang_rad)
        py = cy - r_inner * math.sin(ang_rad)
        sym = planet_symbols.get(p['name'], p['name'][0])
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="12" fill="#fff" stroke="#555" stroke-width="1"/>')
        svg.append(f'<text x="{px:.1f}" y="{py + 1:.1f}" font-size="16" text-anchor="middle" fill="#000" alignment-baseline="middle">{sym}</text>')
    svg.append('</svg>')
    st.markdown(
        f'<div style="display:flex;justify-content:center;margin-top:10px;">{"".join(svg)}</div>',
        unsafe_allow_html=True
    )


def display_horoscope_results(data):
    create_planet_table(data.get('/planet-position', []))
    create_svg_chart(data.get('/planet-position', []))

st.set_page_config(page_title="Zářivá duše • Astrologický horoskop", layout="centered")
st.markdown(
    """
    <h1 style='text-align:center;color:#33cfcf;'>Zářivá duše • Astrologický horoskop</h1>
    <h3 style='text-align:center;color:#33cfcf;'>Vaše hvězdná mapa narození</h3>
    """,
    unsafe_allow_html=True
)

with st.form("astro_form"):
    datum = st.text_input("Datum narození (YYYY-MM-DD)", "1990-01-01")
    cas = st.text_input("Čas narození (HH:MM)", "12:00")
    mesto = st.selectbox("Město narození", list(gelocations.keys()))
    submit = st.form_submit_button("Vypočítat horoskop")

if submit:
    try:
        if not validate_datetime(datum, cas):
            raise ValueError("Špatný formát data nebo času.")
        poz = gelocations[mesto]
        dt = format_datetime_for_api(datum, cas)
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
        if not all_data.get('/planet-position'):
            raise RuntimeError("Nepodařilo se získat astrologická data.")
        display_horoscope_results(all_data)
    except Exception as e:
        st.error(f"Chyba: {e}")
        st.text(traceback.format_exc())

st.markdown(
    '<div style="text-align:center;font-size:0.9em;margin-top:2em;">Powered by <a href="https://developer.prokerala.com/" target="_blank">Prokerala Astrology API</a></div>',
    unsafe_allow_html=True
)
