import streamlit as st
import requests
import datetime
import json
from urllib.parse import urlencode
import time
import numpy as np
import plotly.graph_objects as go

# Konstanty pro API
PROKERALA_CLIENT_ID = "a299b037-8f17-4973-94ec-2ff6181170c9"
PROKERALA_CLIENT_SECRET = "uDo6680pyltTVtUI5Wu9q16sHUoeScGTsz5UunYr"
API_BASE_URL = "https://api.prokerala.com/v2/astrology"


def get_access_token():
    """Získá přístupový token pro Prokerala API"""
    url = "https://api.prokerala.com/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": PROKERALA_CLIENT_ID,
        "client_secret": PROKERALA_CLIENT_SECRET,
    }
    try:
        response = requests.post(url, data=data, timeout=30)
        response.raise_for_status()
        token_data = response.json()
        return token_data.get("access_token")
    except Exception as e:
        st.error(f"Chyba při získávání tokenu: {e}")
        return None


def call_prokerala_api(endpoint, params):
    """Volá Prokerala API s danými parametry"""
    token = get_access_token()
    if not token:
        return None
    headers = {"Authorization": f"Bearer {token}"}
    url = f"{API_BASE_URL}{endpoint}?{urlencode(params)}"
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Chyba API: {e}")
        return None


def validate_datetime(datum, cas):
    try:
        datetime.datetime.strptime(f"{datum} {cas}", "%Y-%m-%d %H:%M")
        return True
    except ValueError:
        return False


def format_datetime_for_api(datum, cas):
    try:
        dt = datetime.datetime.strptime(f"{datum} {cas}", "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+01:00"
    except ValueError:
        return None


def create_planet_table(planet_data):
    st.subheader("📋 Tabulka planet")
    if isinstance(planet_data, dict) and "planet_position" in planet_data:
        planets_list = planet_data["planet_position"]
    else:
        st.error("Neočekávaná struktura dat pro planety")
        return
    symbols = {"Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
               "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
               "Ascendant":"ASC","Rahu":"☊","Ketu":"☋"}
    zodiac = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
              "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    ayanamsa = 23.9
    rows = []
    for p in planets_list:
        lon = (p.get("longitude",0) + ayanamsa) % 360
        idx = int(lon // 30)
        sign = zodiac[idx]
        deg = lon % 30
        d_int = int(deg)
        minutes = int((deg-d_int)*60)
        rows.append({
            "Planet": f"{symbols.get(p['name'],p['name'])} {p['name']}",
            "Sign": sign,
            "Degree": f"{d_int}°{minutes:02d}'",
            "House": p.get("position","N/A"),
            "Motion": "Retrograde" if p.get("is_retrograde",False) else "Direct"
        })
    import pandas as pd
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)
    col1, col2, col3 = st.columns(3)
    col1.metric("Celkem planet", len(rows))
    retro = sum(1 for r in rows if r["Motion"]=="Retrograde")
    col2.metric("Retrográdní", retro)
    col3.metric("Přímý pohyb", len(rows)-retro)


def create_chart_visualization(planet_data):
    """Interaktivní astrologické kolo pomocí Plotly"""
    st.subheader("🔮 Vaše astrologické kolo")
    if not (isinstance(planet_data, dict) and "planet_position" in planet_data):
        st.info("Vizualizace není dostupná")
        return
    # Připrav data
    ayanamsa = 23.9
    thetas, texts = [], []
    symbols = {"Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀",
               "Mars":"♂","Jupiter":"♃","Saturn":"♄","Uranus":"♅",
               "Neptune":"♆","Pluto":"♇","Ascendant":"ASC","Rahu":"☊","Ketu":"☋"}
    for p in planet_data["planet_position"]:
        lon = (p.get("longitude",0) + ayanamsa) % 360
        thetas.append(lon)
        texts.append(symbols.get(p.get("name"), p.get("name")))
    # Vykreslení
    fig = go.Figure()
    # dvanáct segmentů
    for i in range(12):
        angle = i*30
        fig.add_shape(
            type="line", x0=0.5, y0=0.5,
            x1=0.5 + 0.45*np.cos(np.deg2rad(angle)),
            y1=0.5 + 0.45*np.sin(np.deg2rad(angle)),
            line=dict(width=1)
        )
    # planety
    fig.add_trace(go.Scatterpolar(
        r=[1]*len(thetas), theta=thetas, mode="text",
        text=texts, textfont=dict(size=18),
        hoverinfo="text", hovertext=[f"{texts[i]}: {thetas[i]:.1f}°" for i in range(len(thetas))]
    ))
    fig.update_layout(
        polar=dict(
            angularaxis=dict(rotation=90, direction="clockwise", showticklabels=False),
            radialaxis=dict(visible=False)
        ),
        showlegend=False, margin=dict(l=0,r=0,t=0,b=0), width=600, height=600
    )
    st.plotly_chart(fig, use_container_width=True)

# Funkce pro zobrazení domů, aspektů atd. zůstávají beze změn

# --- Ostatní funkce (display_houses, display_aspects, display_horoscope_results) ---
# Pro úsporu místa je vynechán repas; zachovávají se původní implementace.

# Konfigurace Streamlit
st.set_page_config(page_title="Zářivá duše • Astrologický horoskop", layout="centered")
st.markdown("""
    <h1 style='text-align: center; color: #33cfcf;'>Zářivá duše • Astrologický horoskop</h1>
    <h3 style='text-align: center; color: #33cfcf;'>Vaše hvězdná mapa narození</h3>
""", unsafe_allow_html=True)

# Formulář
with st.form("astro_form"):
    datum = st.text_input("Datum narození (YYYY-MM-DD)", value="1990-01-01")
    cas = st.text_input("Čas narození (HH:MM)", value="12:00")
    mesto = st.selectbox("Město narození", list(geolokace.keys()))
    submit = st.form_submit_button("Vypočítat horoskop")

if submit:
    if not validate_datetime(datum, cas):
        st.error("Neplatný formát data nebo času.")
        st.stop()
    poloha = geolokace[mesto]
    formatted = format_datetime_for_api(datum, cas)
    if not formatted:
        st.error("Chyba při formátování data a času")
        st.stop()
    # Získání dat
    params = {"datetime": formatted, "coordinates": f"{poloha['latitude']},{poloha['longitude']}",
              "ayanamsa": 1, "house_system": "placidus", "orb": "default",
              "timezone": poloha['timezone']}
    all_data = {}
    c = 0
    for ep in ["/planet-position","/birth-details","/kundli"]:
        data = call_prokerala_api(ep, params)
        if data and "data" in data:
            all_data[ep] = data["data"]
            c += 1
        time.sleep(1)
    if c>0:
        # výsledky
        create_planet_table(all_data.get("/planet-position", {}))
        create_chart_visualization(all_data.get("/planet-position", {}))
        # zde volání display_houses, display_aspects...
    else:
        st.error("Nepodařilo se získat astrologická data.")

# Patička
st.markdown(
    '<div style="text-align: center; font-size: 0.9em; margin-top: 2em;">'
    'Powered by <a href="https://developer.prokerala.com/" target="_blank">Prokerala Astrology API</a>'
    '</div>',
    unsafe_allow_html=True
)
