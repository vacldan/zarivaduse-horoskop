import swisseph as swe

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

def deg_to_sign(deg):
    sign_num = int(deg // 30)
    sign_deg = deg % 30
    sign = ZODIAC_SIGNS[sign_num]
    deg_int = int(sign_deg)
    min_int = int((sign_deg - deg_int) * 60)
    sec_int = int((((sign_deg - deg_int) * 60) - min_int) * 60)
    return f"{deg_int}°{min_int:02d}′{sec_int:02d}″ {sign}"

# Datum a čas – POZOR, ZADÁVEJ VŽDY V UT!
year, month, day, hour = 1970, 1, 1, 9.0   # 09:00 UT

# Souřadnice Londýn (z Astroseek)
lat = 51.5167    # 51°31′N
lon = -0.1333    # 0°8′W (West = minus!)

jd = swe.julday(year, month, day, hour)

planets = [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN, swe.URANUS, swe.NEPTUNE, swe.PLUTO]
names = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

print("Planet\t\tDegree\t\tSign")
for idx, planet in enumerate(planets):
    lon_deg = swe.calc_ut(jd, planet)[0][0]
    print(f"{names[idx]:<10}\t{lon_deg:.2f}°\t{deg_to_sign(lon_deg)}")

# Domy a ascendent
cusps, ascmc = swe.houses(jd, lat, lon)
print("\nAscendent:", deg_to_sign(ascmc[0]))
print("MC (Medium Coeli):", deg_to_sign(ascmc[1]))
print("\nHouses cusps:")
for i, c in enumerate(cusps, 1):
    print(f"House {i}: {deg_to_sign(c)}")
