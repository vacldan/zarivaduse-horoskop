import streamlit as st
import requests
import datetime
import json
import time
import numpy as np
from urllib.parse import urlencode
import plotly.graph_objects as go
import pandas as pd

# Konstanty pro API
PROKERALA_CLIENT_ID = "a299b037-8f17-4973-94ec-2ff6181170c9"
PROKERALA_CLIENT_SECRET = "uDo6680pyltTVtUI5Wu9q16sHUoeScGTsz5UunYr"
API_BASE_URL = "https://api.prokerala.com/v2/astrology"

# Geolokační data pro města
geolokace = {
    "Praha": {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
    # ... dalších  měst podle potřeby ...
    "Přerov": {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"}
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
    if not planets:
        st.error("Žádná data planet")
        return
    symbols = {"Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
               "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
               "Ascendant":"ASC","Rahu":"☊","Ketu":"☋"}
    zodiac = ["Aries","Taurus","Gemini","Cancer","Leo","Virgo",
              "Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces"]
    ayanamsa = 23.9
    rows = []
    for p in planets:
        lon = (p.get("longitude", 0) + ayanamsa) % 360
        idx = int(lon // 30)
        sign = zodiac[idx]
        deg = lon % 30
        d_int = int(deg)
        minutes = int((deg - d_int) * 60)
        rows.append({
            "Planet": f"{symbols.get(p['name'], p['name'])} {p['name']}",
            "Sign": sign,
            "Degree": f"{d_int}°{minutes:02d}'",
            "House": p.get("position", "N/A"),
            "Motion": "Retrograde" if p.get("is_retrograde", False) else "Direct"
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def create_chart_visualization(planets):
    st.subheader("🔮 Astrologické kolo")
    if not planets:
        st.info("Vizualizace není dostupná")
        return
    symbols = {"Sun":"☉","Moon":"☽","Mercury":"☿","Venus":"♀","Mars":"♂",
               "Jupiter":"♃","Saturn":"♄","Uranus":"♅","Neptune":"♆","Pluto":"♇",
               "Ascendant":"ASC","Rahu":"☊","Ketu":"☋"}
    ayanamsa = 23.9
    thetas, labels = [], []
    for p in planets:
        lon = (p.get("longitude",0) + ayanamsa) % 360
        thetas.append(lon)
        labels.append(symbols.get(p['name'], p['name']))

    fig = go.Figure()
    # Segmenty znamení
    for i, glyph in enumerate(["♈","♉","♊","♋","♌","♍","♎","♏","♐","♑","♒","♓"]):
        angle = i*30
        fig.add_shape(
            type="line",
            x0=0.5, y0=0.5,
            x1=0.5 + 0.45*np.cos(np.deg2rad(angle)),
            y1=0.5 + 0.45*np.sin(np.deg2rad(angle)),
            line=dict(width=1)
        )
        # popisek znamení
        fig.add_annotation(
            x=0.5 + 0.53*np.cos(np.deg2rad(angle+15)),
            y=0.5 + 0.53*np.sin(np.deg2rad(angle+15)),
            text=glyph,
            showarrow=False,
            font=dict(size=18)
        )
    # Planety
    fig.add_trace(go.Scatterpolar(
        r=[1]*len(thetas),
        theta=thetas,
        mode="text",
        text=labels,
        textfont=dict(size=18),
        hoverinfo="text",
        hovertext=[f"{labels[i]}: {thetas[i]:.1f}°" for i in range(len(thetas))]
    ))
    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=False),
            angularaxis=dict(rotation=90, direction="clockwise", showticklabels=False)
        ),
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        width=600,
        height=600
    )
    st.plotly_chart(fig, use_container_width=True)


def display_horoscope_results(data):
    planets = data.get('/planet-position', [])
    create_planet_table(planets)
    create_chart_visualization(planets)
    # případně další sekce (domy, aspekty)

# Streamlit UI
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
    for ep in ["/planet-position", "/birth-details", "/kundli"]:
        d = call_prokerala_api(ep, params)
        if d:
            all_data[ep] = d
        time.sleep(1)
    if all_data.get('/planet-position'):
        display_horoscope_results(all_data)
    else:
        st.error("Nepodařilo se získat astrologická data.")

st.markdown(
    '<div style="text-align:center;font-size:0.9em;margin-top:2em;">Powered by <a href="https://developer.prokerala.com/" target="_blank">Prokerala Astrology API</a></div>',
    unsafe_allow_html=True
)
