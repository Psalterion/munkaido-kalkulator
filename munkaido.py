import streamlit as st
import pandas as pd
import datetime
import calendar
import pdfplumber
import re
import unicodedata

# --- KONFIGURÁCIÓ ---
TEAMS_RULES = {
    "1. Csapat": {"weekend_work": "even"},
    "2. Csapat": {"weekend_work": "odd"}
}

# Név összerendelés
PEOPLE_DATA = {
    "VIS": {"team": "1. Csapat", "fingera_name": "Váradi István"},
    "RE":  {"team": "1. Csapat", "fingera_name": "Váradi René"},
    "MÁ":  {"team": "1. Csapat", "fingera_name": "Máté Arpád"},
    "JK":  {"team": "1. Csapat", "fingera_name": "Jakus Klaudia"},
    "TK":  {"team": "1. Csapat", "fingera_name": "Takács Kristián"},
    "VIN": {"team": "2. Csapat", "fingera_name": "Vitko Norbert"},
    "VT":  {"team": "2. Csapat", "fingera_name": "Vitko Tamás"},
    "VCS": {"team": "2. Csapat", "fingera_name": "Varga Csaba"},
    "ME":  {"team": "2. Csapat", "fingera_name": "Manetová Erika"}
}

HOLIDAYS_2026 = [
    "2026-01-01", "2026-01-06", "2026-04-03", "2026-04-06", 
    "2026-05-01", "2026-05-08", "2026-07-05", "2026-08-29", 
    "2026-09-01", "2026-09-15", "2026-11-01", "2026-11-17", "2026-12-24", "2026-12-25", "2026-12-26"
]

# --- SEGÉDFÜGGVÉNYEK ---
def normalize_text(text):
    """Eltávolítja az ékezeteket és kisbetűsít a könnyebb keresésért."""
    if not text: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                  if unicodedata.category(c) != 'Mn').lower()

def parse_time_str(time_str):
    """Idő szöveg (pl. +54:56) konvertálása decimálisra."""
    if not time_str: return 0.0
    
    sign = 1
    clean_str = time_str.strip()
    if clean_str.startswith('-'):
        sign = -1
        clean_str = clean_str[1:]
    elif clean_str.startswith('+'):
        clean_str = clean_str[1:]
        
    try:
        parts = clean_str.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        return sign * (hours + (minutes / 60.0))
    except:
        return 0.0

def extract_all_balances(pdf_file):
    """
    Végigmegy a PDF-en, és kigyűjti minden megtalált ember egyenlegét.
    JAVÍTVA: Nem írja felül 0-val, ha az összesítő oldalon újra megtalálja a nevet.
    """
    extracted_data = {}
    
    # Kereső tábla: Normalizált név -> Kód (pl. "varadi istvan" -> "VIS")
    norm_name_to_code = {normalize_text(v['fingera_name']): k for k, v in PEOPLE_DATA.items()}
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            # Az oldal szövegét is normalizáljuk a kereséshez
            text_norm = normalize_text(text)
            
            # Megnézzük, kik vannak ezen az oldalon
            found_codes_on_page = []
            for norm_name, code in norm_name_to_code.items():
                if norm_name in text_norm:
                    found_codes_on_page.append(code)
            
            # Minden talált emberre megpróbáljuk kivenni az adatot
            for code in found_codes_on_page:
                # EREDETI (nem normalizált) szövegben keressük a számot a regex-szel
                # Keresés: "Prenášaný nadčas do nasledujúceho mesiaca" + esetleges szóközök + szám
                match = re.search(r"Prenášaný nadčas do nasledujúceho mesiaca\s*([+-]?\d+:\d+)", text)
                
                if match:
                    # Ha találtunk érvényes számot, elmentjük
                    value = parse_time_str(match.group(1))
                    extracted_data[code] = value
                
                # FONTOS: Nincs "else: extracted_data[code] = 0.0"
                # Így ha az összefoglaló oldalon nem talál számot, nem rontja el a korábbi találatot.

    return extracted_data

def calculate_monthly_hours(year, month, team_name):
    """Kiszámolja egy adott csapat havi tervezett munkaóráját és a kötelezőt."""
    team_rule = TEAMS_RULES[team_name]["weekend_work"]
    num_days = calendar.monthrange(year, month)[1]
    
    total_planned = 0
    workdays_count = 0 
    
    for day in range(1, num_days + 1):
        current_date = datetime.date(year, month, day)
        week_num = current_date.isocalendar()[1]
        weekday = current_date.weekday()
        is_even_week = (week_num % 2 == 0)
        is_holiday = current_date.strftime("%Y-%m-%d") in HOLIDAYS_2026
        
        if weekday < 5 and not is_holiday:
            workdays_count += 1

        is_long_week = False
        if team_rule == "even" and is_even_week: is_long_week = True
        elif team_rule == "odd" and not is_even_week: is_long_week = True
            
        status = "Munka"
        if not is_long_week and (weekday == 0 or weekday >= 5): 
            status = "SZABAD"
        
        day_hours = 0
        if status == "Munka":
            weekday_len = (7 + 40/60) - 0.5
            weekend_len = (6 + 10/60) - 0.5
            
            if is_holiday or weekday >= 5:
                day_hours = round(weekend_len, 2)
            else:
                day_hours = round(weekday_len, 2)
        
        total_planned += day_hours
        
    return total_planned, workdays_count * 8

# --- UI ---
st.set_page_config(page_title="Műszak Összesítő", layout="wide")
st.title("📅 Csoportos Műszak és Zárás Tervező")

col_y, col_m = st.columns(2)
with col_y:
    selected_year = st.number_input("Tervezett Év", 2024, 2030, 2026)
with col_m:
    selected_month = st.selectbox("Tervezett Hónap", range(1, 13), index=0)

tab1, tab2 = st.tabs(["👥 Havi Beosztás (Naptár)", "📊 Összesített Zárás Tervező (PDF-ből)"])

with tab1:
    st.subheader("Részletes Napi Beosztás")
    team_view = st.selectbox("Csapat kiválasztása", list(TEAMS_RULES.keys()))
    planned, oblig = calculate_monthly_hours(selected_year, selected_month, team_view)
    st.info(f"Ebben a hónapban a {team_view} tervezett óraszáma: **{planned:.2f} óra** (Kötelező alap: {oblig} óra)")

with tab2:
    st.subheader(f"Várható Zárás Előrejelzés: {selected_year}. {selected_month}. hó")
    st.markdown("Töltsd fel az **előző havi** Fingera export PDF-et.")
    
    uploaded_file = st.file_uploader("Fingera PDF Feltöltése", type=['pdf'])
    
    if uploaded_file:
        with st.spinner('PDF feldolgozása...'):
            balances = extract_all_balances(uploaded_file)
            
            if not balances:
                st.error("Nem találtam ismert nevet a PDF-ben. Biztos jót töltöttél fel?")
            else:
                results = []
                for code, person_info in PEOPLE_DATA.items():
                    name = person_info['fingera_name']
                    team = person_info['team']
                    
                    # Hozott egyenleg
                    start_balance = balances.get(code, 0.0)
                    has_data = code in balances
                    
                    # Tervezett
                    planned_hours, obligation = calculate_monthly_hours(selected_year, selected_month, team)
                    
                    # Eredmény
                    end_balance = start_balance + planned_hours - obligation
                    
                    results.append({
                        "Kód": code,
                        "Név": name,
                        "Csapat": team,
                        "Hozott Egyenleg": start_balance,
                        "Tervezett Munka": planned_hours,
                        "Havi Kötelező": obligation,
                        "Várható Záró": end_balance,
                        "Állapot": "✅" if has_data else "⚠️ Nincs adat"
                    })
                
                df_results = pd.DataFrame(results)
                
                st.success("Számítás kész!")
                
                def color_negative_red(val):
                    color = '#ff4b4b' if val < 0 else '#21c354' # Piros vagy Zöld
                    return f'color: {color}; font-weight: bold'

                st.dataframe(
                    df_results.style.format({
                        "Hozott Egyenleg": "{:.2f}",
                        "Tervezett Munka": "{:.2f}",
                        "Várható Záró": "{:.2f}"
                    }).applymap(color_negative_red, subset=['Várható Záró']),
                    use_container_width=True
                )
                
                csv = df_results.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Táblázat Letöltése (CSV)",
                    data=csv,
                    file_name=f'zaro_elorejelzes_{selected_year}_{selected_month}.csv',
                    mime='text/csv',
                )
