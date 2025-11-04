import streamlit as st
import requests
import datetime
import math
from urllib.parse import urlencode
import pandas as pd
import traceback

# ---------------------------
#  API & CONFIG
# ---------------------------

API_BASE_URL = "https://api.prokerala.com/v2/astrology"

# Barvy elementů
element_colors = {
    "Aries": "#ffe6e6", "Leo": "#ffe6e6", "Sagittarius": "#ffe6e6",
    "Taurus": "#e6ffe6", "Virgo": "#e6ffe6", "Capricorn": "#e6ffe6",
    "Gemini": "#e6e6ff", "Libra": "#e6e6ff", "Aquarius": "#e6e6ff",
    "Cancer": "#e6ffff", "Scorpio": "#e6ffff", "Pisces": "#e6ffff"
}

# Symboly planet
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

# Znamení a glyphy
zodiac = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
glyphs = ["♈", "♉", "♊", "♋", "♌", "♍", "♎", "♏", "♐", "♑", "♒", "♓"]


# ---------------------------
#  DATA: MĚSTA Z CSV
# ---------------------------

@st.cache_data
def load_geolocations_from_csv():
    """
    Načte česká města z obce.csv.
    Snaží se odhadnout sloupce pro název, šířku a délku.
    Když se něco pokazí, vrátí jen Prahu a Přerov.
    """
    try:
        df = pd.read_csv("obce.csv")

        name_col = None
        lat_col = None
        lon_col = None

        for col in df.columns:
            cl = col.lower()
            if name_col is None and any(k in cl for k in ["obec", "mesto", "město", "nazev", "název", "city"]):
                name_col = col
            if lat_col is None and "lat" in cl:
                lat_col = col
            if lon_col is None and (cl == "lon" or "lng" in cl or "long" in cl or "délka" in cl or "delka" in cl):
                lon_col = col

        # fallback – první tři sloupce
        if not (name_col and lat_col and lon_col):
            cols = list(df.columns)
            if len(cols) < 3:
                raise ValueError("Soubor obce.csv nemá dost sloupců.")
            name_col, lat_col, lon_col = cols[0], cols[1], cols[2]

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

        if not geolocations:
            raise ValueError("V obce.csv se nepodařilo vytvořit žádné geolokace.")

        return geolocations

    except Exception as e:
        st.warning(
            f"Nelze korektně načíst obce z obce.csv ({e}). "
            f"Použiji základní seznam měst."
        )
        return {
            "Praha":  {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
            "Přerov": {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"},
        }


geolocations = load_geolocations_from_csv()
city_options = sorted(geolocations.keys())


# ---------------------------
#  API TOKEN
# ---------------------------

def get_access_token():
    """Načte klíče ze Streamlit secrets a vrátí přístupový token."""
    try:
        client_id = st.secrets["PROKERALA_CLIENT_ID"]
        client_secret = st.secrets["PROKERALA_CLIENT_SECRET"]
    except Exception:
        st.error(
            "Chybí PROKERALA_CLIENT_ID nebo PROKERALA_CLIENT_SECRET ve Streamlit Secrets. "
            "Otevři v nastavení aplikace sekci *Secrets* a doplň je."
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


# ---------------------------
#  FETCH PLANET POSITIONS
# ---------------------------

@st.cache_data(ttl=3600)
def fetch_planet_positions(params):
    token = get_access_token()
    if not token:
        return None
    try:
        resp = requests.get(
            f"{API_BASE_URL}/planet-position?{urlencode(params)}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json().get("data")
        return data.get("planet_position")
    except Exception as e:
        st.error(f"Chyba při načítání planet: {e}")
        return None


# ---------------------------
#  DATETIME HELPERS
# ---------------------------

def validate_datetime(d, t):
    try:
        datetime.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        return True
    except Exception:
        return False


def format_datetime_for_api(d, t):
    try:
        dt = datetime.datetime.strptime(f"{d} {t}", "%Y-%m-%d %H:%M")
        # Pozn.: případně můžeš dopočítat offset z timezone, teď je napevno +01:00
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+01:00"
    except Exception:
        return None


# ---------------------------
#  TABULKA PLANET
# ---------------------------

def create_planet_table(planets):
    st.subheader("📋 Tabulka planet")
    if not isinstance(planets, list):
        st.error("Data planet nejsou ve správném formátu.")
        return

    ay = 23.9  # ayanamsa
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

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


# ---------------------------
#  SVG KRUH
# ---------------------------

def create_svg_chart(planets):
    st.subheader("🔮 Astrologické kolo")
    if not isinstance(planets, list):
        st.info("Žádná data k vizualizaci.")
        return

    size = 450
    cx = cy = size / 2
    r_out = size * 0.45
    r_in = r_out * 0.9
    ay = 23.9

    svg = [(
        f'<svg width="{size}" height="{size}" xmlns="http://www.w3.org/2000/svg" '
        'style="background:#fff;border-radius:10px;box-shadow:0 2px 6px rgba(0,0,0,0.15)">'
    )]

    # znamení
    for i, sign in enumerate(zodiac):
        start = math.radians(90 - i * 30)
        end = math.radians(90 - (i + 1) * 30)
        x1 = cx + r_out * math.cos(start)
        y1 = cy - r_out * math.sin(start)
        x2 = cx + r_out * math.cos(end)
        y2 = cy - r_out * math.sin(end)
        col = element_colors.get(sign, "#f0f0f0")
        path = f"M{cx},{cy} L{x1:.1f},{y1:.1f} A{r_out},{r_out} 0 0,1 {x2:.1f},{y2:.1f} Z"
        svg.append(f'<path d="{path}" fill="{col}" stroke="none"/>')

    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r_out}" stroke="#888" stroke-width="2" fill="none"/>')
    svg.append(f'<circle cx="{cx}" cy="{cy}" r="{r_in}" stroke="#ccc" stroke-width="1" fill="none"/>')

    # glyphy znamení
    for i, g in enumerate(glyphs):
        ang = math.radians(90 - (i * 30 + 15))
        gx = cx + (r_out + 20) * math.cos(ang)
        gy = cy - (r_out + 20) * math.sin(ang)
        svg.append(
            f'<text x="{gx:.1f}" y="{gy:.1f}" font-size="18" '
            f'text-anchor="middle" fill="#444">{g}</text>'
        )

    # planety
    for p in planets:
        lon = (p.get("longitude", 0) + ay) % 360
        ang = math.radians(90 - lon)
        px = cx + r_in * math.cos(ang)
        py = cy - r_in * math.sin(ang)
        sym = planet_symbols.get(p["name"], p["name"][0])
        svg.append(
            f'<circle cx="{px:.1f}" cy="{py:.1f}" r="12" fill="#fff" '
            f'stroke="#555" stroke-width="1"/>'
        )
        svg.append(
            f'<text x="{px:.1f}" y="{py+1:.1f}" font-size="16" '
            f'text-anchor="middle" fill="#000">{sym}</text>'
        )

    svg.append("</svg>")

    st.markdown(
        f'<div style="display:flex;justify-content:center;margin-top:10px;">{"".join(svg)}</div>',
        unsafe_allow_html=True,
    )


def display_horoscope_results(planets):
    create_planet_table(planets)
    create_svg_chart(planets)


# ---------------------------
#  UI
# ---------------------------

st.set_page_config(page_title="Zářivá duše • Astrologický horoskop", layout="centered")

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
        dt = format_datetime_for_api(datum, cas)

        params = {
            "datetime": dt,
            "coordinates": f"{poz['latitude']},{poz['longitude']}",
            "ayanamsa": 1,
            "house_system": "placidus",
            "orb": "default",
            "timezone": poz["timezone"],
        }

        planets = fetch_planet_positions(params)

        if planets is None:
            st.error("Nepodařilo se načíst data planet. Zkontroluj API údaje nebo to zkus znovu.")
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
