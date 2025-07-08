import streamlit as st
import pandas as pd
import swisseph as swe
from datetime import datetime
import pytz
import os
import matplotlib.pyplot as plt
import numpy as np
import io

# Znamení pro popisky
ZODIAC_SIGNS = [
    "Beran", "Býk", "Blíženci", "Rak", "Lev", "Panna",
    "Váhy", "Štír", "Střelec", "Kozoroh", "Vodnář", "Ryby"
]
ZODIAC_GLYPHS = [
    u"\u2648", u"\u2649", u"\u264A", u"\u264B", u"\u264C", u"\u264D",
    u"\u264E", u"\u264F", u"\u2650", u"\u2651", u"\u2652", u"\u2653"
]
PLANET_GLYPHS = [
    u"\u2609",  # Slunce
    u"\u263D",  # Luna
    u"\u263F",  # Merkur
    u"\u2640",  # Venuše
    u"\u2642",  # Mars
    u"\u2643",  # Jupiter
    u"\u2644",  # Saturn
    u"\u2645",  # Uran
    u"\u2646",  # Neptun
    u"\u2647",  # Pluto
]
PLANET_NAMES = ["Slunce", "Luna", "Merkur", "Venuše", "Mars", "Jupiter", "Saturn", "Uran", "Neptun", "Pluto"]

def deg_to_sign_full(deg):
    sign_num = int(deg // 30)
    sign_deg = deg % 30
    deg_int = int(sign_deg)
    min_int = int((sign_deg - deg_int) * 60)
    sec_int = int((((sign_deg - deg_int) * 60) - min_int) * 60)
    glyph = ZODIAC_GLYPHS[sign_num]
    sign = ZODIAC_SIGNS[sign_num]
    return glyph, sign, f"{deg_int}°{min_int:02d}′{sec_int:02d}″"

def get_house(lon, cusps):
    houses = list(cusps) + [cusps[0]+360]
    lon = lon % 360
    for i in range(12):
        start = houses[i] % 360
        end = houses[i+1] % 360
        # Ošetření pro domy přes 0°
        if start < end:
            if start <= lon < end:
                return i+1
        else:
            if lon >= start or lon < end:
                return i+1
    return 12

# Načti databázi měst (tvůj CSV!)
file_path = "obce.csv"
if not os.path.exists(file_path):
    st.error("Soubor 'obce.csv' nebyl nalezen! Ulož svůj soubor se seznamem měst do stejné složky jako app.py.")
    st.stop()

df = pd.read_csv(file_path)
df.columns = [c.replace('"','') for c in df.columns]
df['city'] = df['city'].str.title()
city_options = [f"{row['city']}, {row['country']}" for idx, row in df.iterrows()]

# --- DESIGN --- #
st.set_page_config(page_title="Zářivá duše • Horoskop", page_icon=":sparkles:", layout="centered")

st.markdown("""
    <style>
        body, .stApp {
            background-color: #fcf9f6 !important;
        }
        .main {
            background-color: #fcf9f6 !important;
        }
        .stButton>button {
            color: #20d0c2 !important;
            border: 2px solid #FFD700;
            background-color: #fff !important;
            font-weight: bold;
            border-radius: 2.3rem;
        }
        .stButton>button:hover {
            background-color: #FFD700 !important;
            color: #fff !important;
            border: 2px solid #FFD700;
        }
        .stTextInput>div>div>input {
            border-radius: 1.3rem;
            border: 2px solid #20d0c2;
        }
        h1, h2, h3, .stMarkdown, label, legend {
            color: #20b9b1 !important;
            text-align: center !important;
            font-family: 'Montserrat', 'Segoe UI', Arial, sans-serif;
        }
        .block-container {
            padding-top: 1.2rem;
        }
        th {
            background: #f9e9c7 !important;
            color: #d48c13 !important;
        }
        td {
            background: #fff8ee !important;
            color: #335 !important;
        }
        .stTable {
            background: transparent !important;
        }
        .stForm {
            background: #fff6ed !important;
            border-radius: 1.7rem !important;
            box-shadow: 0 6px 32px #efd49a28;
            padding: 2.1rem 1.5rem 0.8rem 1.5rem !important;
        }
        .css-1v0mbdj {padding-top: 0.5rem;}
        /* Skryje warning/žlutá pole Streamlit */
        .stAlert, .stException, .stWarning {
            display: none !important;
            visibility: hidden !important;
            height: 0px !important;
        }
        /* Extra vycentrování loga */
        .logo-center {
            display: flex;
            justify-content: center;
            margin-bottom: 0.1rem;
            margin-top: 1.0rem;
        }
    </style>
""", unsafe_allow_html=True)

# Logo Zářivé duše (musí být ve stejné složce jako app.py)
logo_path = "zariva_duse.png"
if os.path.exists(logo_path):
    st.markdown(
        f"""<div class="logo-center">
        <img src="data:image/png;base64,{(open(logo_path, "rb").read()).hex()}" style="width:120px;"/>
        </div>""",
        unsafe_allow_html=True
    )
else:
    st.warning("Chybí logo Zářivé duše! (ulož jej do složky s názvem zariva_duse.png)")

st.markdown('<h1 style="color:#20b9b1; font-size:2.5rem; font-family: Montserrat; text-align:center;">Zářivá duše • Astrologický horoskop</h1>', unsafe_allow_html=True)
st.markdown('<h3 style="color:#20b9b1; font-size:1.5rem; margin-bottom:1.8rem; text-align:center;">Vaše hvězdná mapa narození</h3>', unsafe_allow_html=True)

with st.form("birth_form"):
    jmeno = st.text_input("Jméno")
    year = st.number_input("Rok narození", min_value=1850, max_value=2050, value=1988, step=1)
    month = st.number_input("Měsíc", min_value=1, max_value=12, value=6, step=1)
    day = st.number_input("Den", min_value=1, max_value=31, value=23, step=1)
    hodina = st.number_input("Hodina narození (0–23, místní čas)", min_value=0, max_value=23, value=12)
    minuta = st.number_input("Minuta", min_value=0, max_value=59, value=0)
    mesto = st.selectbox("Město narození", options=city_options, index=city_options.index("Prague, Czechia") if "Prague, Czechia" in city_options else 0)
    odeslat = st.form_submit_button("Spočítat horoskop")

if odeslat:
    mesto_radek = df.iloc[city_options.index(mesto)]
    lat = float(mesto_radek['lat'])
    lon = float(mesto_radek['lng'])

    tz = pytz.timezone('Europe/Prague')

    try:
        dt_local = datetime(int(year), int(month), int(day), int(hodina), int(minuta))
        dt_localized = tz.localize(dt_local)
        dt_utc = dt_localized.astimezone(pytz.utc)
        hour_utc = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600
    except Exception as e:
        st.error(f"Chyba ve zpracování data/času: {e}")
        st.stop()

    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour_utc)

    # Výpočet planet, domů a pohybu
    planets = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO]
    planet_data = []
    planet_angles = []
    planet_houses = []
    cusps, ascmc = swe.houses(jd, lat, lon, b'P')

    for idx, planet in enumerate(planets):
        lon_deg, speed = swe.calc_ut(jd, planet)[0][0], swe.calc_ut(jd, planet)[0][3]
        glyph, sign, deg_str = deg_to_sign_full(lon_deg)
        house = get_house(lon_deg, cusps)
        motion = "Retrográdní" if speed < 0 else "Direktní"
        planet_data.append({
            "Planeta": f"{PLANET_GLYPHS[idx]} {PLANET_NAMES[idx]}",
            "Znamení": f"{glyph} {sign}",
            "Stupeň": deg_str,
            "Dům": str(house),
            "Pohyb": motion
        })
        planet_angles.append(lon_deg)
        planet_houses.append(house)

    # Výstup: Přehledná tabulka planet
    st.markdown("<h3 style='color:#20b9b1;text-align:center;'>Tabulka pozic planet, domů a pohybu</h3>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(planet_data), use_container_width=True, hide_index=True)

    # Výstup: Přehled domů
    houses_data = []
    for i, c in enumerate(cusps):
        glyph, sign, deg_str = deg_to_sign_full(c)
        houses_data.append({
            "Dům": f"{i+1}",
            "Znamení": f"{glyph} {sign}",
            "Začátek domu": deg_str
        })
    st.markdown("<h3 style='color:#20b9b1;text-align:center;'>Začátky domů a jejich znamení</h3>", unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(houses_data), use_container_width=True, hide_index=True)

    # ----------- ASTROLOGICKÝ KRUH -------------
    fig, ax = plt.subplots(figsize=(8,8), subplot_kw={'projection': 'polar'})
    ax.set_theta_zero_location("E")
    ax.set_theta_direction(-1)
    ax.set_yticklabels([])
    ax.set_xticklabels([])
    ax.grid(False)
    ax.spines['polar'].set_color('#20b9b1')
    ax.spines['polar'].set_linewidth(2.5)
    ax.set_facecolor('#fcf9f6')
    ax.set_title("Astrologický kruh", fontsize=21, color="#20d0c2", pad=22, weight="bold")

    # Znamení - jemné sektory (zlaté/šedé čáry každých 30°)
    for i in range(12):
        theta = np.deg2rad(360 - (i*30) + 90)
        ax.plot([theta, theta], [0, 1.17], color="#e3bc7c", lw=1.8, zorder=1, alpha=0.66)

    # Jemné dělení na 5° (tečky)
    for i in range(72):
        theta = np.deg2rad(360 - (i*5) + 90)
        ax.plot([theta, theta], [0.99, 1.04], color="#d0e5e5", lw=0.7, alpha=0.4, zorder=1)

    # Domy (tenká zlatá čára)
    for i, cusp in enumerate(cusps):
        theta = np.deg2rad(360 - cusp + 90)
        ax.plot([theta, theta], [0, 1.12], color="#222", lw=1.0, alpha=0.65, zorder=2)
        ax.text(theta, 1.15, str(i+1), color="#222", fontsize=13, ha='center', va='center', fontweight="bold", zorder=3, alpha=0.6)

    # Symboly znamení - větší, čitelné, zlaté stíny
    for i in range(12):
        theta = np.deg2rad(360 - (i*30) + 75)
        ax.text(theta, 1.08, ZODIAC_GLYPHS[i], fontsize=34, ha='center', va='center', color="#20b9b1", fontweight="bold", zorder=3, path_effects=None)

    # Planety (výrazné tyrkysové body)
    for i, lon_deg in enumerate(planet_angles):
        theta = np.deg2rad(360 - lon_deg + 90)
        ax.plot(theta, 1.015, 'o', markersize=24, color="#20d0c2", alpha=0.93, markeredgecolor="#fff6ed", markeredgewidth=3, zorder=10)
        ax.text(theta, 1.08, PLANET_GLYPHS[i], fontsize=23, ha='center', va='center', color="#233", zorder=11, fontweight="bold")

    ax.set_rlim([0, 1.18])
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight", transparent=True)
    st.markdown("<h3 style='color:#20b9b1;text-align:center;'>Astrologický kruh</h3>", unsafe_allow_html=True)
    st.image(buf.getvalue(), use_container_width=True)
    plt.close(fig)
