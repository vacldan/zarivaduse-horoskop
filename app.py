import streamlit as st
import requests
import datetime
import json
from urllib.parse import urlencode
import time

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
        if "access_token" in token_data:
            return token_data["access_token"]
        else:
            st.error("Neplatná odpověď při získávání tokenu")
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Chyba při připojení k API: {e}")
        return None
    except json.JSONDecodeError:
        st.error("Neplatná JSON odpověď při získávání tokenu")
        return None

def call_prokerala_api(endpoint, params):
    """Volá Prokerala API s danými parametry"""
    token = get_access_token()
    if not token:
        return None
        
    headers = {
        "Authorization": f"Bearer {token}",
    }
    
    url = f"{API_BASE_URL}{endpoint}?{urlencode(params)}"
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Chyba API (Status {response.status_code}): {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Chyba při volání API: {e}")
        return None
    except json.JSONDecodeError:
        st.error("Neplatná JSON odpověď z API")
        return None

def validate_datetime(datum, cas):
    """Validuje datum a čas"""
    try:
        datetime.datetime.strptime(f"{datum} {cas}", "%Y-%m-%d %H:%M")
        return True
    except ValueError:
        return False

def format_datetime_for_api(datum, cas, timezone="Europe/Prague"):
    """Formátuje datetime pro API ve správném formátu"""
    try:
        dt = datetime.datetime.strptime(f"{datum} {cas}", "%Y-%m-%d %H:%M")
        return dt.strftime("%Y-%m-%dT%H:%M:%S") + "+01:00"
    except ValueError:
        return None

def create_planet_table(planet_data):
    """Vytvoří tabulku planet s korekcí na tropickou astrologii"""
    
    st.subheader("📋 Tabulka planet")
    
    # Kontrola struktury dat
    if isinstance(planet_data, dict) and "planet_position" in planet_data:
        planets_list = planet_data["planet_position"]
    elif isinstance(planet_data, list):
        planets_list = planet_data
    else:
        st.error("Neočekávaná struktura dat pro planety")
        return
    
    # Symboly planet
    planet_symbols = {
        "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
        "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅", "Neptune": "♆", "Pluto": "♇",
        "Ascendant": "ASC", "Rahu": "☊", "Ketu": "☋"
    }
    
    # Západní znamení
    zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                   "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    
    # KLÍČOVÁ OPRAVA: Ayanamsa pro konverzi vedické->tropické
    ayanamsa_1988 = 23.9
    
    # Převod do tabulky
    table_data = []
    
    for planet in planets_list:
        if isinstance(planet, dict):
            name = planet.get("name", "Unknown")
            symbol = planet_symbols.get(name, "")
            
            # Vedická longitude z API
            vedic_longitude = planet.get("longitude", 0)
            
            # KONVERZE NA TROPICKOU: Přidáme ayanamsa
            tropical_longitude = vedic_longitude + ayanamsa_1988
            if tropical_longitude >= 360:
                tropical_longitude -= 360
            
            # Západní znamení podle tropické longitude
            sign_index = int(tropical_longitude // 30)
            western_sign = zodiac_signs[sign_index] if 0 <= sign_index < 12 else "Unknown"
            
            # Stupeň v rámci tropického znamení
            degree_in_sign = tropical_longitude % 30
            deg_int = int(degree_in_sign)
            minutes = int((degree_in_sign - deg_int) * 60)
            degree_formatted = f"{deg_int}°{minutes:02d}'"
            
            # Dům
            house = planet.get("position", planet.get("house", "N/A"))
            
            # Retrográdní pohyb
            is_retrograde = planet.get("is_retrograde", planet.get("retrograde", False))
            motion = "Retrograde" if is_retrograde else "Direct"
            
            table_data.append({
                "Planet": f"{symbol} {name}",
                "Sign": western_sign,
                "Degree": degree_formatted,
                "House": str(house),
                "Motion": motion
            })
    
    if table_data:
        import pandas as pd
        df = pd.DataFrame(table_data)
        
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        # Statistiky
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Celkem planet", len(table_data))
        
        with col2:
            retrograde_count = sum(1 for row in table_data if "Retrograde" in row["Motion"])
            st.metric("Retrográdní", retrograde_count)
        
        with col3:
            direct_count = len(table_data) - retrograde_count
            st.metric("Přímý pohyb", direct_count)
        
        # Retrográdní planety
        if retrograde_count > 0:
            retrograde_planets = [row["Planet"] for row in table_data if "Retrograde" in row["Motion"]]
            st.warning(f"⚠️ Retrográdní planety: {', '.join(retrograde_planets)}")

def create_chart_visualization(planet_data):
    """Vytvoří krásnou vizualizaci astrologického kruhu"""
    
    st.subheader("🔮 Astrologický kruh")
    
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        
        # Získáme data o planetách
        if isinstance(planet_data, dict) and "planet_position" in planet_data:
            planets_list = planet_data["planet_position"]
        else:
            st.info("Vizualizace není dostupná pro tuto strukturu dat")
            return
        
        # Nastavení stylu
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        fig.patch.set_facecolor('white')
        
        # Nastavení kruhu
        ax.set_theta_zero_location('E')  # 0° na východě (Aries)
        ax.set_theta_direction(-1)  # Proti směru hodinových ručiček
        
        # Znamení a jejich barvy
        zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                       "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        
        sign_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD',
                      '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9', '#F8C471', '#82E0AA']
        
        # Pozice znamení (každé znamení má 30°)
        sign_positions = np.linspace(0, 2*np.pi, 13)[:-1]
        
        # Vykreslení segmentů znamení
        for i, (sign, color) in enumerate(zip(zodiac_signs, sign_colors)):
            theta_start = sign_positions[i] - np.pi/12
            theta_end = sign_positions[i] + np.pi/12
            theta_segment = np.linspace(theta_start, theta_end, 50)
            
            # Lehký barevný segment pro každé znamení
            ax.fill_between(theta_segment, 0.8, 1.2, alpha=0.15, color=color)
        
        # Barvy planet
        planet_colors = {
            "Sun": "#FFD700", "Moon": "#C0C0C0", "Mercury": "#FFA500", "Venus": "#FF69B4", 
            "Mars": "#FF4500", "Jupiter": "#8A2BE2", "Saturn": "#2F4F4F", 
            "Uranus": "#4FD0E3", "Neptune": "#4169E1", "Pluto": "#8B4513",
            "Ascendant": "#000000", "Rahu": "#708090", "Ketu": "#696969"
        }
        
        # Symboly planet
        symbols = {"Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", 
                  "Mars": "♂", "Jupiter": "♃", "Saturn": "♄", "Uranus": "♅",
                  "Neptune": "♆", "Pluto": "♇", "Ascendant": "ASC", "Rahu": "☊", "Ketu": "☋"}
        
        # Vykreslení planet s tropickou korekcí
        ayanamsa_1988 = 23.9  # Ayanamsa pro rok 1988
        
        for planet in planets_list:
            if isinstance(planet, dict):
                name = planet.get("name", "")
                vedic_longitude = planet.get("longitude", 0)
                
                # KONVERZE: Vedická -> Tropická longitude
                tropical_longitude = vedic_longitude + ayanamsa_1988
                if tropical_longitude >= 360:
                    tropical_longitude -= 360
                
                # Převod na radiány
                theta = np.radians(tropical_longitude)
                
                # Symbol a barva planety
                symbol = symbols.get(name, name[:3])
                color = planet_colors.get(name, "#333333")
                
                # Vykreslení planety
                ax.plot(theta, 1, 'o', markersize=15, color=color, markeredgecolor='white', markeredgewidth=2)
                ax.text(theta, 1.15, symbol, ha='center', va='center', fontsize=12, fontweight='bold', color='black')
                
                # Přidáme stupně pro důležité planety
                if name in ["Sun", "Moon", "Ascendant"]:
                    degree = tropical_longitude % 30
                    ax.text(theta, 0.85, f"{degree:.0f}°", ha='center', va='center', fontsize=9, color='gray')
        
        # Označení znamení
        for i, sign in enumerate(zodiac_signs):
            ax.text(sign_positions[i], 1.35, sign, ha='center', va='center', 
                   fontsize=11, fontweight='bold', color='#2C3E50')
        
        # Označení stupňů
        degree_positions = np.arange(0, 360, 30)
        for deg in degree_positions:
            theta_deg = np.radians(deg)
            ax.text(theta_deg, 1.45, f"{deg}°", ha='center', va='center', 
                   fontsize=8, alpha=0.6, color='#7F8C8D')
        
        # Nastavení os
        ax.set_ylim(0, 1.6)
        ax.set_rticks([])
        ax.grid(True, alpha=0.3)
        ax.set_title("Astrologický kruh - Pozice planet", fontsize=14, fontweight='bold', pad=20)
        
        # Zobraz graf
        st.pyplot(fig)
        plt.close()
        
        # Přidej textovou reprezentaci pod graf
        display_text_chart(planet_data)
        
    except ImportError:
        st.warning("⚠️ Matplotlib není dostupný pro vizualizaci kruhu.")
        display_text_chart(planet_data)
    except Exception as e:
        st.error(f"Chyba při vytváření vizualizace: {e}")
        display_text_chart(planet_data)

def display_text_chart(planet_data):
    """Zobrazí textovou reprezentaci astrologického kruhu s tropickou korekcí"""
    
    if isinstance(planet_data, dict) and "planet_position" in planet_data:
        planets_list = planet_data["planet_position"]
    else:
        return
    
    zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                   "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    
    # Seskupení planet podle tropických znamení
    signs_with_planets = {}
    ayanamsa_1988 = 23.9  # Ayanamsa pro rok 1988
    
    for planet in planets_list:
        if isinstance(planet, dict):
            name = planet.get("name", "")
            vedic_longitude = planet.get("longitude", 0)
            
            # Převod na tropickou longitude
            tropical_longitude = vedic_longitude + ayanamsa_1988
            if tropical_longitude >= 360:
                tropical_longitude -= 360
                
            sign_index = int(tropical_longitude // 30)
            
            if 0 <= sign_index < 12:
                sign = zodiac_signs[sign_index]
                degree = tropical_longitude % 30
                
                if sign not in signs_with_planets:
                    signs_with_planets[sign] = []
                
                signs_with_planets[sign].append(f"{name} ({degree:.1f}°)")
    
    # Zobrazení
    st.write("**Rozložení planet ve znameních (Tropická astrologie):**")
    for sign in zodiac_signs:
        if sign in signs_with_planets:
            planets_str = ", ".join(signs_with_planets[sign])
            st.write(f"**{sign}:** {planets_str}")
        else:
            st.write(f"**{sign}:** (prázdné)")

def display_houses(planet_data):
    """Zobrazí informace o astrologických domech"""
    
    st.subheader("🏠 Astrologické domy")
    
    # Pokusíme se vypočítat domy z Ascendentu
    if isinstance(planet_data, dict) and "planet_position" in planet_data:
        planets_list = planet_data["planet_position"]
        ascendant_longitude = None
        
        # Najdeme Ascendent
        for planet in planets_list:
            if isinstance(planet, dict) and planet.get("name") == "Ascendant":
                ascendant_longitude = planet.get("longitude", 0)
                break
        
        if ascendant_longitude is not None:
            zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                           "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
            
            house_meanings = [
                "Osobnost, Já, vzhled, identita",
                "Majetek, hodnoty, peníze, hmotné jistoty", 
                "Komunikace, sourozenci, krátké cesty, vzdělání",
                "Domov, rodina, kořeny, bydlení",
                "Kreativita, děti, láska, zábava",
                "Zdraví, práce, služba, denní rutina",
                "Partnerství, manželství, vztahy, nepřátelé",
                "Transformace, smrt, okultno, společné finance",
                "Filozofie, cestování, vzdělání, víra", 
                "Kariéra, postavení, reputace, cíle",
                "Přátelé, naděje, skupiny, ideály",
                "Tajnosti, spiritualita, vězení, nepřátelé"
            ]
            
            col1, col2 = st.columns(2)
            
            for i in range(12):
                house_longitude = (ascendant_longitude + (i * 30)) % 360
                sign_index = int(house_longitude // 30)
                sign = zodiac_signs[sign_index]
                degree = house_longitude % 30
                meaning = house_meanings[i]
                
                with col1 if i % 2 == 0 else col2:
                    st.write(f"**{i+1}. dům:** {sign} {degree:.0f}°")
                    st.write(f"   _{meaning}_")
                    st.write("---")
            
            # Přidáme informaci o planetách v domech
            st.subheader("🪐 Planety v domech")
            
            # Seskupíme planety podle domů
            houses_with_planets = {}
            
            for planet in planets_list:
                if isinstance(planet, dict):
                    name = planet.get("name", "")
                    house_num = planet.get("position", 0)
                    
                    if house_num and house_num != "N/A":
                        house_num = int(house_num) if isinstance(house_num, str) and house_num.isdigit() else house_num
                        
                        if house_num not in houses_with_planets:
                            houses_with_planets[house_num] = []
                        
                        houses_with_planets[house_num].append(name)
            
            if houses_with_planets:
                col1, col2 = st.columns(2)
                
                for house_num in sorted(houses_with_planets.keys()):
                    if isinstance(house_num, int) and 1 <= house_num <= 12:
                        planets_in_house = houses_with_planets[house_num]
                        meaning = house_meanings[house_num - 1] if house_num <= len(house_meanings) else "N/A"
                        
                        with col1 if house_num % 2 == 1 else col2:
                            st.write(f"**{house_num}. dům:** {', '.join(planets_in_house)}")
                            st.write(f"   _{meaning.split(',')[0]}_")
                            st.write("---")
            else:
                st.info("Informace o pozicích planet v domech nejsou v API dostupné")
        else:
            display_house_meanings_only()
    else:
        display_house_meanings_only()

def display_house_meanings_only():
    """Zobrazí pouze významy domů jako fallback"""
    
    house_meanings = [
        ("1. dům (Ascendant)", "Osobnost, Já, vzhled, identita, první dojem"),
        ("2. dům", "Majetek, hodnoty, peníze, hmotné jistoty, sebehodnocení"), 
        ("3. dům", "Komunikace, sourozenci, krátké cesty, místní prostředí"),
        ("4. dům (IC)", "Domov, rodina, kořeny, bydlení, soukromí"),
        ("5. dům", "Kreativita, děti, láska, zábava, koníčky"),
        ("6. dům", "Zdraví, práce, služba, denní rutina, zvířata"),
        ("7. dům (Descendant)", "Partnerství, manželství, vztahy, otevření nepřátelé"),
        ("8. dům", "Transformace, smrt, okultno, společné finance, dědictví"),
        ("9. dům", "Filozofie, cestování, vzdělání, víra, zákon"), 
        ("10. dům (MC)", "Kariéra, postavení, reputace, cíle, společenský status"),
        ("11. dům", "Přátelé, naděje, skupiny, ideály, přání"),
        ("12. dům", "Tajnosti, spiritualita, vězení, skryté nepřátelé, podvědomí")
    ]
    
    st.info("Významy astrologických domů:")
    
    col1, col2 = st.columns(2)
    
    for i, (house, meaning) in enumerate(house_meanings):
        with col1 if i % 2 == 0 else col2:
            st.write(f"**{house}**")
            st.write(f"_{meaning}_")
            st.write("---")

def display_additional_info(birth_data):
    """Zobrazí dodatečné informace z birth-details"""
    
    st.subheader("ℹ️ Dodatečné informace")
    
    # Pouze základní informace, ne vedické
    if isinstance(birth_data, dict):
        col1, col2 = st.columns(2)
        
        basic_info = ["birth_time", "sunrise", "sunset", "day_duration", "night_duration"]
        
        with col1:
            for field in basic_info[:3]:
                if field in birth_data:
                    label = field.replace('_', ' ').title()
                    st.write(f"**{label}:** {birth_data[field]}")
        
        with col2:
            for field in basic_info[3:]:
                if field in birth_data:
                    label = field.replace('_', ' ').title()
                    st.write(f"**{label}:** {birth_data[field]}")

def display_horoscope_results(all_data):
    """Zobrazí výsledky horoskopu - kombinuje data z více zdrojů"""
    
    st.header("🌟 Váš astrologický horoskop")
    
    # Kombinujeme data z více zdrojů pro kompletní planety
    combined_planet_data = None
    
    # Priorita: planet-position > kundli > birth-details
    for key in ["/planet-position", "/kundli", "/birth-details"]:
        if key in all_data:
            data = all_data[key]
            if isinstance(data, dict) and ("planet_position" in data or "planets" in data):
                combined_planet_data = data
                break
    
    if combined_planet_data:
        # Tabulka planet
        create_planet_table(combined_planet_data)
        
        # Kruhový astrologický diagram
        create_chart_visualization(combined_planet_data)
        
        # Astrologické domy
        display_houses(combined_planet_data)
        
        # Aspekty (pokud jsou dostupné)
        if "aspects" in combined_planet_data:
            st.subheader("🔗 Planetární aspekty")
            display_aspects(combined_planet_data)
    
    # Dodatečné informace z birth-details (pouze základní časové info)
    birth_data = all_data.get("/birth-details")
    if birth_data and birth_data != combined_planet_data:
        # Zobrazíme jen základní časové informace, ne vedické
        if isinstance(birth_data, dict):
            basic_fields = ["birth_time", "sunrise", "sunset", "day_duration", "night_duration"]
            has_basic = any(field in birth_data for field in basic_fields)
            
            if has_basic:
                st.subheader("ℹ️ Informace o dni")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if "sunrise" in birth_data:
                        st.write(f"**Východ slunce:** {birth_data['sunrise']}")
                    if "day_duration" in birth_data:
                        st.write(f"**Délka dne:** {birth_data['day_duration']}")
                
                with col2:
                    if "sunset" in birth_data:
                        st.write(f"**Západ slunce:** {birth_data['sunset']}")
                    if "night_duration" in birth_data:
                        st.write(f"**Délka noci:** {birth_data['night_duration']}")

def display_aspects(planet_data):
    """Zobrazí planetární aspekty pokud jsou dostupné"""
    
    aspects_data = planet_data.get("aspects", [])
    
    if aspects_data and isinstance(aspects_data, list):
        st.info("**Hlavní planetární aspekty:**")
        
        # Symboly aspektů
        aspect_symbols = {
            "conjunction": "☌", "opposition": "☍", "trine": "△", 
            "square": "□", "sextile": "⚹", "quincunx": "⚻"
        }
        
        # Symboly planet
        planet_symbols = {
            "Sun": "☉", "Moon": "☽", "Mercury": "☿", "Venus": "♀", "Mars": "♂",
            "Jupiter": "♃", "Saturn": "♄", "Ascendant": "ASC"
        }
        
        col1, col2 = st.columns(2)
        
        for i, aspect in enumerate(aspects_data):
            if isinstance(aspect, dict):
                planet1 = aspect.get("planet1", "")
                planet2 = aspect.get("planet2", "")
                aspect_type = aspect.get("type", aspect.get("aspect", ""))
                orb = aspect.get("orb", "")
                
                # Symboly
                p1_symbol = planet_symbols.get(planet1, planet1[:3])
                p2_symbol = planet_symbols.get(planet2, planet2[:3])
                aspect_symbol = aspect_symbols.get(aspect_type.lower(), aspect_type)
                
                with col1 if i % 2 == 0 else col2:
                    st.write(f"**{p1_symbol} {aspect_symbol} {p2_symbol}**")
                    st.write(f"_{planet1} {aspect_type} {planet2}_")
                    if orb:
                        st.write(f"Orb: {orb}°")
                    st.write("---")
    else:
        st.info("Informace o aspektech nejsou v API dostupné")
        st.write("""
        **Hlavní aspekty v astrologii:**
        - **Konjunkce (0°)** - spojení energií
        - **Opozice (180°)** - napětí, polarita  
        - **Trigon (120°)** - harmonie, tok energie
        - **Kvadrát (90°)** - výzva, dynamické napětí
        - **Sextil (60°)** - příležitost, podpora
        - **Quincunx (150°)** - adjustace, nejistota
        """)

# Konfigurace stránky
st.set_page_config(page_title="Zářivá duše • Astrologický horoskop", layout="centered")

# Hlavička
st.markdown("""
    <h1 style='text-align: center; color: #33cfcf;'>Zářivá duše • Astrologický horoskop</h1>
    <h3 style='text-align: center; color: #33cfcf;'>Vaše hvězdná mapa narození</h3>
""", unsafe_allow_html=True)

# Jednoduchý formulář
with st.form("astro_form"):
    datum = st.text_input("Datum narození (YYYY-MM-DD)", value="1990-01-01")
    cas = st.text_input("Čas narození (HH:MM)", value="12:00")
    
    mesto = st.selectbox("Město narození", [
        "Praha", "Brno", "Ostrava", "Plzeň", "Liberec", "Olomouc", "Ústí nad Labem", 
        "Hradec Králové", "České Budějovice", "Pardubice", "Zlín", "Havířov", 
        "Kladno", "Most", "Opava", "Frýdek-Místek", "Karviná", "Jihlava", 
        "Teplice", "Děčín", "Karlovy Vary", "Jablonec nad Nisou", "Mladá Boleslav",
        "Prostějov", "Přerov", "Česká Lípa", "Třebíč", "Uherské Hradiště",
        "Trutnov", "Chomutov", "Kolín", "Jirkov", "Ústí nad Orlicí",
        "Bratislava", "Košice", "Prešov", "Žilina", "Banská Bystrica", "Nitra",
        "Trnava", "Martin", "Trenčín", "Poprad", "Prievidza", "Zvolen",
        "Považská Bystrica", "Michalovce", "Spišská Nová Ves", "Komárno",
        "Levice", "Humenné", "Bardejov", "Liptovský Mikuláš"
    ])

    # Přesné geolokační data s časovými pásmy
    geolokace = {
        "Praha": {"latitude": 50.0755, "longitude": 14.4378, "timezone": "Europe/Prague"},
        "Brno": {"latitude": 49.1951, "longitude": 16.6068, "timezone": "Europe/Prague"},
        "Ostrava": {"latitude": 49.8209, "longitude": 18.2625, "timezone": "Europe/Prague"},
        "Plzeň": {"latitude": 49.7384, "longitude": 13.3736, "timezone": "Europe/Prague"},
        "Liberec": {"latitude": 50.7663, "longitude": 15.0543, "timezone": "Europe/Prague"},
        "Olomouc": {"latitude": 49.5938, "longitude": 17.2509, "timezone": "Europe/Prague"},
        "Ústí nad Labem": {"latitude": 50.6607, "longitude": 14.0322, "timezone": "Europe/Prague"},
        "Hradec Králové": {"latitude": 50.2092, "longitude": 15.8327, "timezone": "Europe/Prague"},
        "České Budějovice": {"latitude": 48.9745, "longitude": 14.4742, "timezone": "Europe/Prague"},
        "Pardubice": {"latitude": 50.0343, "longitude": 15.7812, "timezone": "Europe/Prague"},
        "Zlín": {"latitude": 49.2233, "longitude": 17.6692, "timezone": "Europe/Prague"},
        "Havířov": {"latitude": 49.7845, "longitude": 18.4373, "timezone": "Europe/Prague"},
        "Kladno": {"latitude": 50.1473, "longitude": 14.1027, "timezone": "Europe/Prague"},
        "Most": {"latitude": 50.5035, "longitude": 13.6357, "timezone": "Europe/Prague"},
        "Opava": {"latitude": 49.9387, "longitude": 17.9027, "timezone": "Europe/Prague"},
        "Frýdek-Místek": {"latitude": 49.6833, "longitude": 18.3500, "timezone": "Europe/Prague"},
        "Karviná": {"latitude": 49.8540, "longitude": 18.5470, "timezone": "Europe/Prague"},
        "Jihlava": {"latitude": 49.3960, "longitude": 15.5915, "timezone": "Europe/Prague"},
        "Teplice": {"latitude": 50.6404, "longitude": 13.8245, "timezone": "Europe/Prague"},
        "Děčín": {"latitude": 50.7821, "longitude": 14.2147, "timezone": "Europe/Prague"},
        "Karlovy Vary": {"latitude": 50.2327, "longitude": 12.8710, "timezone": "Europe/Prague"},
        "Jablonec nad Nisou": {"latitude": 50.7243, "longitude": 15.1712, "timezone": "Europe/Prague"},
        "Mladá Boleslav": {"latitude": 50.4113, "longitude": 14.9033, "timezone": "Europe/Prague"},
        "Prostějov": {"latitude": 49.4718, "longitude": 17.1118, "timezone": "Europe/Prague"},
        "Přerov": {"latitude": 49.4558, "longitude": 17.4509, "timezone": "Europe/Prague"},
        "Česká Lípa": {"latitude": 50.6859, "longitude": 14.5373, "timezone": "Europe/Prague"},
        "Třebíč": {"latitude": 49.2147, "longitude": 15.8820, "timezone": "Europe/Prague"},
        "Uherské Hradiště": {"latitude": 49.0697, "longitude": 17.4622, "timezone": "Europe/Prague"},
        "Trutnov": {"latitude": 50.5611, "longitude": 15.9127, "timezone": "Europe/Prague"},
        "Chomutov": {"latitude": 50.4607, "longitude": 13.4175, "timezone": "Europe/Prague"},
        "Kolín": {"latitude": 50.0282, "longitude": 15.1998, "timezone": "Europe/Prague"},
        "Jirkov": {"latitude": 50.4997, "longitude": 13.4497, "timezone": "Europe/Prague"},
        "Ústí nad Orlicí": {"latitude": 49.9742, "longitude": 16.3939, "timezone": "Europe/Prague"},
        "Bratislava": {"latitude": 48.1486, "longitude": 17.1077, "timezone": "Europe/Bratislava"},
        "Košice": {"latitude": 48.7164, "longitude": 21.2611, "timezone": "Europe/Bratislava"},
        "Prešov": {"latitude": 49.0018, "longitude": 21.2393, "timezone": "Europe/Bratislava"},
        "Žilina": {"latitude": 49.2231, "longitude": 18.7397, "timezone": "Europe/Bratislava"},
        "Banská Bystrica": {"latitude": 48.7370, "longitude": 19.1480, "timezone": "Europe/Bratislava"},
        "Nitra": {"latitude": 48.3081, "longitude": 18.0711, "timezone": "Europe/Bratislava"},
        "Trnava": {"latitude": 48.3774, "longitude": 17.5887, "timezone": "Europe/Bratislava"},
        "Martin": {"latitude": 49.0665, "longitude": 18.9211, "timezone": "Europe/Bratislava"},
        "Trenčín": {"latitude": 48.8946, "longitude": 18.0446, "timezone": "Europe/Bratislava"},
        "Poprad": {"latitude": 49.0615, "longitude": 20.2988, "timezone": "Europe/Bratislava"},
        "Prievidza": {"latitude": 48.7739, "longitude": 18.6270, "timezone": "Europe/Bratislava"},
        "Zvolen": {"latitude": 48.5748, "longitude": 19.1453, "timezone": "Europe/Bratislava"},
        "Považská Bystrica": {"latitude": 49.1203, "longitude": 18.4148, "timezone": "Europe/Bratislava"},
        "Michalovce": {"latitude": 48.7542, "longitude": 21.9153, "timezone": "Europe/Bratislava"},
        "Spišská Nová Ves": {"latitude": 48.9483, "longitude": 20.5659, "timezone": "Europe/Bratislava"},
        "Komárno": {"latitude": 47.7615, "longitude": 18.1270, "timezone": "Europe/Bratislava"},
        "Levice": {"latitude": 48.2147, "longitude": 18.6058, "timezone": "Europe/Bratislava"},
        "Humenné": {"latitude": 48.9394, "longitude": 21.9062, "timezone": "Europe/Bratislava"},
        "Bardejov": {"latitude": 49.2918, "longitude": 21.2733, "timezone": "Europe/Bratislava"},
        "Liptovský Mikuláš": {"latitude": 49.0833, "longitude": 19.6167, "timezone": "Europe/Bratislava"}
    }
    
    submit = st.form_submit_button("Vypočítat horoskop")

# Zpracování formuláře
if submit:
    # Validace vstupů
    if not validate_datetime(datum, cas):
        st.error("Neplatný formát data nebo času. Použijte formát YYYY-MM-DD pro datum a HH:MM pro čas.")
        st.stop()
    
    poloha = geolokace[mesto]
    
    # Formátování datetime pro API
    formatted_datetime = format_datetime_for_api(datum, cas)
    if not formatted_datetime:
        st.error("Chyba při formátování data a času")
        st.stop()
    
    # Získáme astrologická data
    all_data = {}
    success_count = 0
    
    # Parametry pro API - použijeme přesné nastavení pro západní astrologii
    api_params = {
        "datetime": formatted_datetime,
        "coordinates": f"{poloha['latitude']},{poloha['longitude']}",
        "ayanamsa": 1,
        "house_system": "placidus",
        "orb": "default",
        "timezone": poloha.get("timezone", "Europe/Prague")
    }
    
    # Zkusíme získat pozice planet
    data = call_prokerala_api("/planet-position", api_params)
    if data and "data" in data:
        all_data["/planet-position"] = data["data"]
        success_count += 1
    
    # Pauza před dalším dotazem
    if success_count > 0:
        time.sleep(2)
    
    # Zkusíme získat detaily narození
    data = call_prokerala_api("/birth-details", api_params)
    if data and "data" in data:
        all_data["/birth-details"] = data["data"]
        success_count += 1
    
    # Zkusíme získat více planet z jiných endpointů
    time.sleep(2)
    
    # Zkusíme kundli endpoint pro více planet
    data = call_prokerala_api("/kundli", api_params)
    if data and "data" in data:
        all_data["/kundli"] = data["data"]
        success_count += 1
    
    # Zobrazení získaných dat
    if success_count > 0:
        display_horoscope_results(all_data)
    else:
        st.error("Nepodařilo se získat astrologická data. Zkuste to znovu za chvíli.")

# Patička
st.markdown(
    '<div style="text-align: center; font-size: 0.9em; margin-top: 2em;">'
    'Powered by <a href="https://developer.prokerala.com/" target="_blank">Prokerala Astrology API</a>'
    '</div>',
    unsafe_allow_html=True
)
