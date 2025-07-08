import streamlit as st
import pandas as pd
import swisseph as swe
from datetime import datetime
import pytz
import os

ZODIAC_SIGNS = [
    "Beran", "Býk", "Blíženci", "Rak", "Lev", "Panna",
    "Váhy", "Štír", "Střelec", "Kozoroh", "Vodnář", "Ryby"
]
def deg_to_sign(deg):
    sign_num = int(deg // 30)
    sign_deg = deg % 30
    sign = ZODIAC_SIGNS[sign_num]
    deg_int = int(sign_deg)
    min_int = int((sign_deg - deg_int) * 60)
    sec_int = int((((sign_deg - deg_int) * 60) - min_int) * 60)
    return f"{deg_int}°{min_int:02d}′{sec_int:02d}″ {sign}"

# Načti databázi měst (ošetření chyby)
file_path = "obce.csv"
if not os.path.exists(file_path):
    st.error("Soubor 'obce.csv' (nebo cities.csv) nebyl nalezen! Ulož svůj soubor se seznamem měst do stejné složky jako app.py.")
    st.stop()

df = pd.read_csv(file_path)
# Některé soubory mají záhlaví v uvozovkách – odeber
df.columns = [c.replace('"','') for c in df.columns]
# Vyber potřebné sloupce (můžeš upravit podle potřeby)
df['city'] = df['city'].str.title()
city_options = [f"{row['city']}, {row['country']}" for idx, row in df.iterrows()]

st.markdown("""
    <style>
        body, .stApp {background-color: #f8fcfc;}
        .stButton>button {color: #20d0c2; border: 2px solid #FFD700; background-color: #fff; font-weight: bold;}
        .stButton>button:hover {background-color: #FFD700; color: #20d0c2;}
        h1, h2, h3, .stMarkdown, label, legend {color: #003f3f;}
    </style>
""", unsafe_allow_html=True)

st.markdown('<h1 style="color:#20d0c2;">Výpočet astrologického horoskopu (světová města)</h1>', unsafe_allow_html=True)
st.markdown('<p style="color:#FFD700;"><strong>Zadávejte vždy místní čas narození. Automaticky převedeme na UT/GMT.</strong></p>', unsafe_allow_html=True)

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
    # Najdi vybrané město
    mesto_radek = df.iloc[city_options.index(mesto)]
    lat = float(mesto_radek['lat'])
    lon = float(mesto_radek['lng'])

    # Výběr časové zóny – pro celosvětový soubor doporučuji ještě upřesnit podle státu/města.
    # Pokud chceš jen ČR/SK, použij Europe/Prague
    tz = pytz.timezone('Europe/Prague')  # Tohle je správně pro CZ/SK. Pro ostatní státy potřebuješ knihovnu timezonefinder!

    try:
        dt_local = datetime(int(year), int(month), int(day), int(hodina), int(minuta))
        dt_localized = tz.localize(dt_local)
        dt_utc = dt_localized.astimezone(pytz.utc)
        hour_utc = dt_utc.hour + dt_utc.minute/60 + dt_utc.second/3600
    except Exception as e:
        st.error(f"Chyba ve zpracování data/času: {e}")
        st.stop()

    jd = swe.julday(dt_utc.year, dt_utc.month, dt_utc.day, hour_utc)

    planets = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO]
    names = ["Slunce", "Luna", "Merkur", "Venuše", "Mars", "Jupiter", "Saturn", "Uran", "Neptun", "Pluto"]

    st.subheader(f"Výsledek pro: {jmeno}, {day:02d}.{month:02d}.{year}, {mesto}")
    st.markdown("### Postavení planet")
    for idx, planet in enumerate(planets):
        lon_deg = swe.calc_ut(jd, planet)[0][0]
        st.write(f"{names[idx]}: {deg_to_sign(lon_deg)}")

    cusps, ascmc = swe.houses(jd, lat, lon, b'P')
    st.markdown("### Domy a ascendent")
    st.write(f"Ascendent: {deg_to_sign(ascmc[0])}")
    st.write(f"MC (Medium Coeli): {deg_to_sign(ascmc[1])}")
    for i, c in enumerate(cusps, 1):
        st.write(f"Dům {i}: {deg_to_sign(c)}")
