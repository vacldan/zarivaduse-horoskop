import streamlit as st
import requests
import datetime
import time
import math
import json
from urllib.parse import urlencode
import pandas as pd

# Konstanty pro API
PROKERALA_CLIENT_ID = "a299b037-8f17-4973-94ec-2ff6181170c9"
PROKERALA_CLIENT_SECRET = "uDo6680pyltTVtUI5Wu9q16sHUoeScGTsz5UunYr"
API_BASE_URL = "https://api.prokerala.com/v2/astrology"

# Geolokační data pro města
geolokace = {
    "Praha":      {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
    "Přerov":     {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"}
    # ... další města ...
}

# Barvy pro elementy
element_colors = {
    "Aries":       "#ffe6e6", "Leo":          "#ffe6e6", "Sagittarius": "#ffe6e6",
    "Taurus":      "#e6ffe6", "Virgo":        "#e6ffe6", "Capricorn":    "#e6ffe6",
    "Gemini":      "#e6e6ff", "Libra":        "#e6e6ff", "Aquarius":     "#e6e6ff",
    "Cancer":      "#e6ffff", "Scorpio":      "#e6ffff", "Pisces":       "#e6ffff"
}

# Symboly planet
planet_symbols = {
    "Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
    "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
    "Ascendant":"ASC","Rahu":"☊","Ketu":"☋"
}
# Západní znamení
zodiac = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
          "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
# Glyphy
glyphs = ["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]


def get_access_token():
    url = "https://api.prokerala.com/token"
    data = {"grant_type": "client_credentials", "client_id": PROKERALA_CLIENT_ID, "client_secret": PROKERALA_CLIENT_SECRET}
    try:
        r = requests.post(url, data=data, timeout=30)
        r.raise_for_status()
        return r.json().get("access_token")
    except Exception as e:
        st.error(f"Chyba tokenu: {e}")
        return None


def call_prokerala_api(endpoint, params):
    token = get_access_token()
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE_URL}{endpoint}?{urlencode(params)}"
    try:
        r = requests.get(url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json().get("data")
    except Exception as e:
        st.error(f"Chyba API: {e}")
        return None


def validate_datetime(d, t):
    try:
        datetime.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        return True
    except ValueError:
        return False


def format_datetime_for_api(d, t):
    try:
        dt = datetime.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+01:00"
    except ValueError:
        return None


def create_planet_table(planets):
    st.subheader("📋 Tabulka planet")
    if isinstance(planets, dict) and "planet_position" in planets:
        pl = planets["planet_position"]
    elif isinstance(planets, list):
        pl = planets
    else:
        st.error("Data planet nejsou ve správném formátu.")
        return
    ay = 23.9
    rows = []
    for p in pl:
        lon = (p.get("longitude", 0) + ay) % 360
        idx = int(lon // 30)
        sign = zodiac[idx]
        deg = lon % 30
        di = int(deg); mi = int((deg - di) * 60)
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
    svg = [f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg" style="background:#fff;border-radius:10px;box-shadow:0 2px 6px rgba(0,0,0,0.15)">']
