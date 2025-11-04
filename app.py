import streamlit as st
import requests
import datetime
import math
import pandas as pd
import traceback
from urllib.parse import urlencode

# --------------------------------------------------
# ZÁKLADNÍ KONFIGURACE
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
    "Rahu": "☊",
    "Ketu": "☋",
    "Ascendant": "ASC",
}

AYANAMSA = 23.9  # stejná korekce jako v tabulce


# --------------------------------------------------
# NAČTENÍ MĚST Z WORLDCITIES / FALLBACK
# --------------------------------------------------

@st.cache_data
def load_geolocations():
    """
    1) Zkusí načíst worldcities.xlsx a vyfiltrovat města v ČR.
    2) Když se cokoliv pokazí, použije fallback s několika městy.
    """
    try:
        df = pd.read_excel("worldcities.xlsx")

        # pokus najít sloupce flexibilně podle názvu
        cols = {c.lower(): c for c in df.columns}

        # city
        city_col = None
        for c in df.columns:
            if "city" in c.lower():
                city_col = c
                break

        # country
        country_col = None
        for c in df.columns:
            if "country" in c.lower():
                country_col = c
                break

        # latitude
        lat_col = None
        for c in df.columns:
            cl = c.lower()
            if "lat" in cl:
                lat_col = c
                break

        # longitude
        lon_col = None
        for c in df.columns:
            cl = c.lower()
            if "lng" in cl or "lon" in cl or "long" in cl:
                lon_col = c
                break

        if not all([city_col, country_col, lat_col, lon_col]):
            raise ValueError("worldcities.xlsx: nenalezeny potřebné sloupce")

        # jen ČR (Czechia / Czech Republic / podobné)
        df_cz = df[df[country_col].astype(str).str.contains("czech", case=False, na=False)]
        df_cz = df_cz.dropna(subset=[city_col, lat_col, lon_col])

        geolocations = {}
        for _, row in df_cz.iterrows():
            name = str(row[city_col])
            geolocations[name] = {
                "latitude": float(row[lat_col]),
                "longitude": float(row[lon_col]),
                "timezone": "Europe/Prague",
            }

        if geolocations:
            return geolocations

    except Exception:
        # cokoliv se nepovede -> fallback níže
        pass

    # Fallback – pár měst, aby appka *vždy* fungovala
    return {
        "Praha":      {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
        "Přerov":     {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"},
        "Mohelnice":  {"latitude": 49.7749, "longitude": 16.9206, "timezone": "Europe/Prague"},
    }


geolocations = load_geolocations()
city_options = sorted(geolocations.keys())


# --------------------------------------------------
# API TOKEN
# --------------------------------------------------

def get_access_token():
    """Načtení Prokerala tokenu ze secrets."""
    try:
        client_id = st.secrets["PROKERALA_CLIENT_ID"]
        client_secret = st.secrets["PROKERALA_CLIENT_SECRET"]
    except Exception:
        st.error(
            "Chybí PROKERALA_CLIENT_ID nebo PROKERALA_CLIENT_SECRET ve Streamlit Secrets. "
            "Doplň je v nastavení aplikace."
        )
        return None

    try:
        resp = requests.post(
            "https://api.prokerala.com/token",
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("access_token")
    except Exception as e:
        st.error(f"Chyba při získávání API tokenu: {e}")
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
        st.error(f"Chyba při načítání dat z API: {e}")
        return None


# --------------------------------------------------
# DATETIME HELPERS
# --------------------------------------------------

def validate_datetime(d, t):
    try:
        datetime.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        return True
    except Exception:
        return False


def format_datetime_for_api(d, t):
    try:
        dt = datetime.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        # Zjednodušeně napevno +01:00 – jsme v Europe/Prague
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+01:00"
    except Exception:
        return None


# --------------------------------------------------
# TABULKA PLANET
# --------------------------------------------------

def create_planet_table(planets):
    st.subheader("📋 Tabulka planet")

    if not isinstance(planets, list):
        st.error("Data planet nejsou ve správném formátu.")
        return

    rows = []
    for p in planets:
        lon = (p.get("longitude", 0) + AYANAMSA) % 360
        idx = int(lon // 30)
        sign = zodiac[idx]
        deg = lon % 30
        di = int(deg)
        mi = int((deg - di) * 60)
        rows.append(
            {
                "Planet": f"{planet_symbols.get(p['name'], p['name'])} {p['name']}",
                "Sign": sign,
                "Degree": f"{di}°{mi:02d}'",
                "House": p.get("position", "?"),
                "Motion": "Retrograde" if p.get("is_retrograde", False) else "Direct",
            }
        )

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


# --------------------------------------------------
# ASPEKTY
# --------------------------------------------------

def compute_aspects(points):
    """
    Vstup: list dictů s keys: name, lon (0–360), theta, x, y
    Výstup: list aspekových čar (x1,y1,x2,y2,color,width)
    """
    aspects = []
    aspect_defs = [
        ("sextile", 60, 5, "#2ecc71", 1.2),
        ("trine", 120, 6, "#3498db", 1.6),
        ("opposition", 180, 6, "#e74c3c", 1.8),
    ]

    allowed = {"Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Rahu", "Ketu"}

    filtered = [p for p in points if p["name"] in allowed]

    for i in range(len(filtered)):
        for j in range(i + 1, len(filtered)):
            p1 = filtered[i]
            p2 = filtered[j]
            diff = abs(p1["lon"] - p2["lon"])
            if diff > 180:
                diff = 360 - diff

            for name, exact, orb, color, width in aspect_defs:
                if abs(diff - exact) <= orb:
                    aspects.append(
                        {
                            "x1": p1["x"],
                            "y1": p1["y"],
                            "x2": p2["x"],
                            "y2": p2["y"],
                            "color": color,
                            "width": width,
                        }
                    )
                    break

    return aspects


# --------------------------------------------------
# SVG GRAF
# --------------------------------------------------

def create_svg_chart(planets):
    st.subheader("🔮 Astrologické kolo")

    if not isinstance(planets, list):
        st.info("Žádná data k vizualizaci.")
        return

    size = 700
    cx = cy = size / 2

    r_outer = size * 0.46      # vnější kruh
    r_tick_inner = r_outer - 6
    r_tick_mid = r_outer - 12
    r_tick_major = r_outer - 20

    r_planets = r_outer * 0.75  # orbita planet
    r_houses_outer = r_planets * 0.95
    r_houses_inner = r_planets * 0.55

    svg = [
        (
            f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg" '
            'style="background:#ffffff;border-radius:18px;box-shadow:0 2px 6px rgba(0,0,0,0.1)">'
        )
    ]

    # vnější kruh
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_outer}" stroke="#222" stroke-width="2" fill="white"/>'
    )

    # --- dělení na stupně (tick marks) ---
    for deg in range(360):
        angle = math.radians(90 - deg)
        if deg % 30 == 0:
            inner = r_tick_major
            stroke = "#000000"
            width = 2
        elif deg % 10 == 0:
            inner = r_tick_mid
            stroke = "#555555"
            width = 1.4
        else:
            inner = r_tick_inner
            stroke = "#999999"
            width = 0.8

        x1 = cx + r_outer * math.cos(angle)
        y1 = cy - r_outer * math.sin(angle)
        x2 = cx + inner * math.cos(angle)
        y2 = cy - inner * math.sin(angle)
        svg.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}"/>'
        )

    # --- symboly znamení ---
    for i, g in enumerate(glyphs):
        ang = math.radians(90 - (i * 30 + 15))
        r_text = r_outer - 35
        gx = cx + r_text * math.cos(ang)
        gy = cy - r_text * math.sin(ang)
        svg.append(
            f'<text x="{gx:.1f}" y="{gy:.1f}" font-size="20" '
            f'text-anchor="middle" dominant-baseline="central" fill="#000000">{g}</text>'
        )

    # --- vnitřní kruh domů ---
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_houses_outer}" stroke="#777777" stroke-width="1" fill="none"/>'
    )
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_houses_inner}" stroke="#dddddd" stroke-width="1" fill="none"/>'
    )

    # domy – rovnoměrné dělení (12 x 30°) + čísla
    for i in range(12):
        angle = math.radians(90 - i * 30)
        x1 = cx + r_houses_outer * math.cos(angle)
        y1 = cy - r_houses_outer * math.sin(angle)
        x2 = cx + r_houses_inner * math.cos(angle)
        y2 = cy - r_houses_inner * math.sin(angle)
        svg.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#777777" stroke-width="1"/>'
        )

        mid_angle = math.radians(90 - (i * 30 + 15))
        r_label = (r_houses_outer + r_houses_inner) / 2
        lx = cx + r_label * math.cos(mid_angle)
        ly = cy - r_label * math.sin(mid_angle)
        svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" '
            f'text-anchor="middle" dominant-baseline="central" fill="#444444">{i+1}</text>'
        )

    # --- logo uprostřed ---
    # soubor logo.png dej do stejné složky jako app.py
    logo_radius = r_houses_inner * 0.8
    logo_size = logo_radius * 2
    logo_x = cx - logo_radius
    logo_y = cy - logo_radius
    svg.append(
        f'<image href="logo.png" x="{logo_x:.1f}" y="{logo_y:.1f}" '
        f'width="{logo_size:.1f}" height="{logo_size:.1f}" opacity="0.98"/>'
    )

    # --- vypočet pozic planet (po ayanamsa) ---
    points = []
    for p in planets:
        lon = (p.get("longitude", 0) + AYANAMSA) % 360
        theta = math.radians(90 - lon)
        px = cx + r_planets * math.cos(theta)
        py = cy - r_planets * math.sin(theta)
        points.append(
            {
                "name": p["name"],
                "lon": lon,
                "theta": theta,
                "x": px,
                "y": py,
            }
        )

    # --- aspekty (čáry uvnitř kola) ---
    aspects = compute_aspects(points)
    for a in aspects:
        svg.append(
            f'<line x1="{a["x1"]:.1f}" y1="{a["y1"]:.1f}" '
            f'x2="{a["x2"]:.1f}" y2="{a["y2"]:.1f}" '
            f'stroke="{a["color"]}" stroke-width="{a["width"]}" '
            f'stroke-linecap="round" opacity="0.85"/>'
        )

    # --- planety (nad aspekty) ---
    for p in points:
        sym = planet_symbols.get(p["name"], p["name"][0])
        svg.append(
            f'<circle cx="{p["x"]:.1f}" cy="{p["y"]:.1f}" r="15" '
            f'fill="#ffffff" stroke="#333333" stroke-width="1.4"/>'
        )
        svg.append(
            f'<text x="{p["x"]:.1f}" y="{p["y"]:.1f}" font-size="16" '
            f'text-anchor="middle" dominant-baseline="central" fill="#000000">{sym}</text>'
        )

    # --- hlavní osy (vizuální kříž) ---
    for axis_angle in [0, 90, 180, 270]:
        ang = math.radians(90 - axis_angle)
        x1 = cx + r_houses_inner * math.cos(ang)
        y1 = cy - r_houses_inner * math.sin(ang)
        x2 = cx + r_outer * math.cos(ang)
        y2 = cy - r_outer * math.sin(ang)
        svg.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="#000000" stroke-width="2"/>'
        )

    svg.append("</svg>")

    st.markdown(
        f'<div style="display:flex;justify-content:center;margin-top:10px;">{"".join(svg)}</div>',
        unsafe_allow_html=True,
    )


def display_horoscope_results(planets):
    create_planet_table(planets)
    create_svg_chart(planets)


# --------------------------------------------------
# UI
# --------------------------------------------------

st.set_page_config(
    page_title="Zářivá duše • Astrologický horoskop", layout="centered"
)

st.markdown(
    """
<h1 style='text-align:center;color:#33cfcf;'>Zářivá duše • Astrologický horoskop</h1>
<h3 style='text-align:center;color:#33cfcf;'>Vaše hvězdná mapa narození</h3>
""",
    unsafe_allow_html=True,
)

with st.form("astro_form"):
    datum = st.text_input("Datum narození (YYYY-MM-DD)", "1990-01-01")
    cas = st.text_input("Čas narození (HH:MM)", "12:00")
    mesto = st.selectbox("Město narození", city_options)
    submit = st.form_submit_button("Vypočítat horoskop")

if submit:
    try:
        if not validate_datetime(datum, cas):
            raise ValueError("Špatný formát data nebo času.")

        poz = geolocations[mesto]
        dt_api = format_datetime_for_api(datum, cas)

        params = {
            "datetime": dt_api,
            "coordinates": f"{poz['latitude']},{poz['longitude']}",
            "ayanamsa": 1,
            "house_system": "placidus",
            "timezone": poz["timezone"],
        }

        planets = fetch_planet_positions(params)

        if planets is None:
            st.error(
                "Nepodařilo se načíst data planet. Zkontroluj API údaje nebo to zkus znovu."
            )
        else:
            display_horoscope_results(planets)

    except Exception as e:
        st.error(f"Chyba: {e}")
        st.text(traceback.format_exc())

st.markdown(
    """
<div style="text-align:center;font-size:0.9em;margin-top:2em;">
Powered by <a href="https://developer.prokerala.com/" target="_blank">Prokerala Astrology API</a>
</div>
""",
    unsafe_allow_html=True,
)
