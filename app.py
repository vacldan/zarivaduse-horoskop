import streamlit as st
import requests
import datetime
import math
import pandas as pd
import traceback
from urllib.parse import urlencode

# --------------------------------------------------
# KONFIGURACE
# --------------------------------------------------

API_BASE_URL = "https://api.prokerala.com/v2/astrology"

zodiac = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
glyphs = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]

planet_symbols = {
    "Sun": "☉",
    "Moon": "☽",
    "Mercury": "☿",
    "Venus": "♀",
    "Mars": "♂",
    "Jupiter": "♃",
    "Saturn": "♄",
    "Uranus": "♅",
    "Neptune": "♆",
    "Pluto": "♇",
    "Ascendant": "ASC",
    "Rahu": "☊",
    "Ketu": "☋",
}


# --------------------------------------------------
# NAČTENÍ MĚST
# --------------------------------------------------

@st.cache_data
def load_geolocations():
    try:
        df = pd.read_csv("obce.csv", sep=None, engine="python")
        df = df.dropna()
        name_col = df.columns[0]
        lat_col = df.columns[1]
        lon_col = df.columns[2]
        geolocations = {
            row[name_col]: {
                "latitude": float(row[lat_col]),
                "longitude": float(row[lon_col]),
                "timezone": "Europe/Prague",
            }
            for _, row in df.iterrows()
        }
        return geolocations
    except Exception:
        st.warning("Nelze načíst obce.csv, použiji základní seznam měst.")
        return {
            "Praha": {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
            "Přerov": {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"},
            "Mohelnice": {"latitude": 49.7749, "longitude": 16.9206, "timezone": "Europe/Prague"},
        }


geolocations = load_geolocations()
city_options = sorted(geolocations.keys())


# --------------------------------------------------
# API TOKEN
# --------------------------------------------------

def get_access_token():
    try:
        client_id = st.secrets["PROKERALA_CLIENT_ID"]
        client_secret = st.secrets["PROKERALA_CLIENT_SECRET"]
    except Exception:
        st.error("Chybí API klíče v sekci Secrets!")
        return None

    try:
        resp = requests.post(
            "https://api.prokerala.com/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        st.error(f"Chyba při získávání tokenu: {e}")
        return None


# --------------------------------------------------
# DATA Z API
# --------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_planet_positions(params):
    token = get_access_token()
    if not token:
        return None
    try:
        r = requests.get(
            f"{API_BASE_URL}/planet-position?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["data"]["planet_position"]
    except Exception as e:
        st.error(f"Chyba API: {e}")
        return None


# --------------------------------------------------
# TABULKA PLANET
# --------------------------------------------------

def create_planet_table(planets):
    st.subheader("📋 Tabulka planet")
    ay = 23.9
    rows = []
    for p in planets:
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
            "Motion": "Retrograde" if p.get("is_retrograde", False) else "Direct",
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# --------------------------------------------------
# SVG GRAF
# --------------------------------------------------

def create_svg_chart(planets):
    st.subheader("🜂 Astrologické kolo")

    size = 700
    cx = cy = size / 2
    r_outer = size * 0.46
    r_inner = r_outer * 0.75
    ay = 23.9

    svg = [f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg" '
           'style="background:white;border-radius:18px;box-shadow:0 2px 6px rgba(0,0,0,0.1)">']

    # Vnější kruh
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" stroke="#222" stroke-width="2" fill="white"/>')

    # --- dělení na stupně (tick marks) ---
    for deg in range(360):
        angle = math.radians(90 - deg)
        outer = r_outer
        if deg % 30 == 0:
            inner = r_outer - 20  # hlavní čára (znamení)
            stroke = "#000"
            width = 2
        elif deg % 10 == 0:
            inner = r_outer - 12  # střední čárky
            stroke = "#555"
            width = 1.5
        else:
            inner = r_outer - 6   # mini čárky po 1°
            stroke = "#999"
            width = 0.8

        x1 = cx + outer * math.cos(angle)
        y1 = cy - outer * math.sin(angle)
        x2 = cx + inner * math.cos(angle)
        y2 = cy - inner * math.sin(angle)
        svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="{stroke}" stroke-width="{width}"/>')

    # --- symboly znamení ---
    for i, g in enumerate(glyphs):
        ang = math.radians(90 - (i * 30 + 15))
        r_text = r_outer - 35
        gx = cx + r_text * math.cos(ang)
        gy = cy - r_text * math.sin(ang)
        svg.append(f'<text x="{gx:.1f}" y="{gy:.1f}" font-size="20" '
                   f'text-anchor="middle" dominant-baseline="central" fill="#000">{g}</text>')

    # --- planety ---
    for p in planets:
        lon = (p.get("longitude", 0) + ay) % 360
        ang = math.radians(90 - lon)
        px = cx + r_inner * math.cos(ang)
        py = cy - r_inner * math.sin(ang)
        sym = planet_symbols.get(p["name"], p["name"][0])
        svg.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="14" fill="white" stroke="#333" stroke-width="1.3"/>')
        svg.append(f'<text x="{px:.1f}" y="{py:.1f}" font-size="15" '
                   f'text-anchor="middle" dominant-baseline="central" fill="#000">{sym}</text>')

    # --- hlavní osy (ASC, MC, DSC, IC) ---
    for axis_angle in [0, 90, 180, 270]:
        ang = math.radians(90 - axis_angle)
        x1 = cx + r_inner * math.cos(ang)
        y1 = cy - r_inner * math.sin(ang)
        x2 = cx + r_outer * math.cos(ang)
        y2 = cy - r_outer * math.sin(ang)
        svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                   f'stroke="#000" stroke-width="2"/>')

    svg.append("</svg>")
    st.markdown(f'<div style="display:flex;justify-content:center;">{"".join(svg)}</div>', unsafe_allow_html=True)


# --------------------------------------------------
# UI
# --------------------------------------------------

st.set_page_config(page_title="Zářivá duše • Horoskop", layout="centered")

st.markdown("""
<h1 style='text-align:center;color:#33cfcf;'>Zářivá duše • Astrologický horoskop</h1>
<h3 style='text-align:center;'>Vaše hvězdná mapa narození</h3>
""", unsafe_allow_html=True)

with st.form("astro_form"):
    datum = st.text_input("Datum narození (YYYY-MM-DD)", "1990-01-01")
    cas = st.text_input("Čas narození (HH:MM)", "12:00")
    mesto = st.selectbox("Město narození", city_options)
    submit = st.form_submit_button("Vypočítat horoskop")

if submit:
    try:
        poz = geolocations[mesto]
        dt = datetime.datetime.strptime(f"{datum} {cas}", "%Y-%m-%d %H:%M")
        datetime_api = dt.strftime("%Y-%m-%dT%H:%M:%S+01:00")

        params = {
            "datetime": datetime_api,
            "coordinates": f"{poz['latitude']},{poz['longitude']}",
            "ayanamsa": 1,
            "house_system": "placidus",
            "timezone": poz["timezone"],
        }

        planets = fetch_planet_positions(params)
        if planets:
            create_planet_table(planets)
            create_svg_chart(planets)
        else:
            st.error("Nepodařilo se načíst data planet.")
    except Exception as e:
        st.error(f"Chyba: {e}")
        st.text(traceback.format_exc())

st.markdown("<div style='text-align:center;margin-top:2em;font-size:0.9em;'>"
            "Powered by <a href='https://developer.prokerala.com/' target='_blank'>Prokerala Astrology API</a></div>",
            unsafe_allow_html=True)
