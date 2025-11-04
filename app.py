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

AYANAMSA = 23.9  # stejné jako v tabulce


# --------------------------------------------------
# NAČTENÍ MĚST Z OBCE.CSV + FALLBACK
# --------------------------------------------------

@st.cache_data
def load_geolocations():
    """
    Hlavní zdroj: obce.csv v rootu repozitáře.
    Snaží se najít sloupce s názvem obce, šířkou a délkou automaticky.
    Když cokoli selže, použije fallback (Praha / Přerov / Mohelnice).
    """
    try:
        df = pd.read_csv("obce.csv", sep=None, engine="python")
        if df.shape[1] < 3 or len(df) == 0:
            raise ValueError("obce.csv nemá dost sloupců/řádků")

        name_col = None
        lat_col = None
        lon_col = None

        for col in df.columns:
            cl = col.lower()
            if name_col is None and any(
                k in cl for k in ["obec", "mesto", "město", "nazev", "název", "city"]
            ):
                name_col = col
            if lat_col is None and "lat" in cl:
                lat_col = col
            if lon_col is None and (
                cl == "lon" or "lng" in cl or "long" in cl or "délka" in cl or "delka" in cl
            ):
                lon_col = col

        # kdyby neprošla heuristika, vezmeme prostě první tři sloupce
        if not (name_col and lat_col and lon_col):
            cols = list(df.columns)
            if len(cols) >= 3:
                name_col, lat_col, lon_col = cols[0], cols[1], cols[2]
            else:
                raise ValueError("obce.csv nemá použitelné sloupce")

        df = df.dropna(subset=[name_col, lat_col, lon_col])

        geolocations = {}
        for _, row in df.iterrows():
            try:
                name = str(row[name_col])
                lat = float(row[lat_col])
                lon = float(row[lon_col])
            except Exception:
                continue
            geolocations[name] = {
                "latitude": lat,
                "longitude": lon,
                "timezone": "Europe/Prague",
            }

        if geolocations:
            return geolocations
        else:
            raise ValueError("obce.csv se načetlo, ale bez dat")

    except Exception:
        # fallback – aby appka vždy něco nabídla
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
            'style="background:#ffffff;border-radius:28px;box-shadow:0 18px 45px rgba(15,23,42,0.08);">'
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
            f'text-anchor="middle" dominant-baseline="central" fill="#7b7c92">{g}</text>'
        )

    # --- vnitřní kruh domů ---
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_houses_outer}" stroke="#d0d2e0" stroke-width="1" fill="none"/>'
    )
    svg.append(
        f'<circle cx="{cx}" cy="{cy}" r="{r_houses_inner}" stroke="#f0f1f8" stroke-width="1" fill="none"/>'
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
            f'stroke="#e0e1ee" stroke-width="1"/>'
        )

        mid_angle = math.radians(90 - (i * 30 + 15))
        r_label = (r_houses_outer + r_houses_inner) / 2
        lx = cx + r_label * math.cos(mid_angle)
        ly = cy - r_label * math.sin(mid_angle)
        svg.append(
            f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="13" '
            f'text-anchor="middle" dominant-baseline="central" fill="#9b9db4">{i+1}</text>'
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
# UI – PAGE CONFIG + GLOBAL STYLING
# --------------------------------------------------

st.set_page_config(
    page_title="Zářivá duše • Astrologický horoskop",
    layout="centered",
    page_icon="✨",
)

# Globální CSS – pastelový design ala landing page
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Poppins', sans-serif;
}

/* Background */
.stApp {
    background: radial-gradient(circle at top left, #ffe9f0 0, #fff7ff 30%, #f3fbff 70%, #ffffff 100%);
}

/* Hlavní karta kolem obsahu */
.main-card {
    max-width: 1100px;
    margin: 0 auto 3rem auto;
    padding: 2.5rem 3rem 3rem 3rem;
    background: rgba(255,255,255,0.96);
    border-radius: 28px;
    box-shadow: 0 18px 45px rgba(15,23,42,0.08);
}

/* Mírně zaoblené rohy pro tabulky a widgety */
div[data-testid="stDataFrame"] {
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 14px 35px rgba(15,23,42,0.08);
}

/* Text input & selectbox */
.stTextInput > div > div > input,
.stSelectbox > div > div > div > div {
    border-radius: 999px !important;
    border: 1px solid #e5e7f5 !important;
    background: #f9f9ff !important;
    padding: 0.55rem 1.1rem !important;
    font-size: 0.95rem !important;
}

.stTextInput > label,
.stSelectbox > label {
    font-weight: 500;
    color: #4b5563;
}

/* Button – gradient CTA */
.stButton > button {
    border-radius: 999px;
    border: none;
    padding: 0.7rem 1.9rem;
    font-weight: 600;
    font-size: 0.95rem;
    background: linear-gradient(90deg,#ff9b73,#ff7ad9);
    color: white;
    box-shadow: 0 12px 25px rgba(249,115,22,0.35);
    transition: all 0.15s ease-out;
}

.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 16px 32px rgba(249,115,22,0.45);
}

/* Subheadery */
h2, h3 {
    color: #15192c;
}

/* Sekce "Tabulka planet" a "Astrologické kolo" – ikona + text víc k sobě */
.block-container {
    padding-top: 2.5rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# --------------------------------------------------
# HERO SEKCE + OBSAH V "KARTĚ"
# --------------------------------------------------

# Hero text
st.markdown(
    """
<div style='text-align:center;margin-bottom:2.0rem;'>
  <h1 style='margin:0;font-size:3.1rem;font-weight:800;color:#33cfcf;letter-spacing:0.08em;'>
    ZÁŘIVÁ DUŠE
  </h1>
  <h2 style='margin:0.35rem 0 0.5rem;font-size:2.2rem;font-weight:700;color:#15192c;'>
    Astrologický horoskop
  </h2>
  <p style='margin:0;font-size:1.1rem;color:#6b7280;'>
    Vaše hvězdná mapa narození – na pár kliknutí, připravená k výkladu.
  </p>
</div>
""",
    unsafe_allow_html=True,
)

# Otevřeme hlavní "card" wrapper
st.markdown("<div class='main-card'>", unsafe_allow_html=True)

# Formulář
st.markdown(
    "<h3 style='margin-top:0;margin-bottom:0.8rem;'>Vyplňte údaje narození</h3>",
    unsafe_allow_html=True,
)

with st.form("astro_form"):
    col1, col2 = st.columns(2)
    with col1:
        datum = st.text_input("Datum narození (YYYY-MM-DD)", "1990-01-01")
    with col2:
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
            st.markdown("<div style='margin-top:2rem;'></div>", unsafe_allow_html=True)
            display_horoscope_results(planets)

    except Exception as e:
        st.error(f"Chyba: {e}")
        st.text(traceback.format_exc())

# Zavřeme hlavní card wrapper
st.markdown("</div>", unsafe_allow_html=True)

# Footer
st.markdown(
    """
<div style="text-align:center;font-size:0.9em;margin-top:2.5rem;color:#9ca3af;">
Powered by <a href="https://developer.prokerala.com/" target="_blank" style="color:#33cfcf;text-decoration:none;">Prokerala Astrology API</a>
</div>
""",
    unsafe_allow_html=True,
)
