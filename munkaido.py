import streamlit as st
import pandas as pd
import datetime
import calendar
import pdfplumber
import re

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

# --- PDF FELDOLGOZÓ MOTOR ---
def parse_time_str(time_str):
    """Átalakítja a '+54:56' formátumot decimális órára (pl. 54.93)."""
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

def extract_fingera_balance(pdf_file, target_name):
    """
    Keresi a nevet, és a hozzá tartozó 'Prenášaný nadčas do nasledujúceho mesiaca' értéket.
    """
    final_balance = 0.0
    found = False
    raw_text_value = ""
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            
            # Ha megtaláljuk a nevet az oldalon
            if target_name.lower() in text.lower():
                found = True
                
                # Keresés: "Prenášaný nadčas do nasledujúceho mesiaca" és az utána jövő idő
                # A PDF szövegében ez gyakran így néz ki: "Prenášaný nadčas do nasledujúceho mesiaca +54:56"
                # Vagy sortöréssel. A regex megpróbálja elkapni a számot.
                
                # 1. Próbálkozás: Közvetlen egyezés
                match = re.search(r"Prenášaný nadčas do nasledujúceho mesiaca\s*([+-]?\d+:\d+)", text)
                
                if match:
                    raw_text_value = match.group(1)
                    final_balance = parse_time_str(raw_text_value)
                    break # Megvan, kiléphetünk
                
    return final_balance, raw_text_value, found

# --- TERVEZŐ LOGIKA (Csak a referencia miatt maradt) ---
def calculate_daily_hours(date_obj, is_holiday, shift_type):
    weekday_hours = (7 + 40/60) - 0.5  
    weekend_hours = (6 + 10/60) - 0.5 
    
    if shift_type == "SZABAD": return 0.0
    if is_holiday or date_obj.weekday() >= 5: return round(weekend_hours, 2)
    else: return round(weekday_hours, 2)

def generate_schedule(year, month, team_name):
    team_rule = TEAMS_RULES[team_name]["weekend_work"]
    num_days = calendar.monthrange(year, month)[1]
    schedule_data = []
    total_hours = 0
    
    for day in range(1, num_days + 1):
        current_date = datetime.date(year, month, day)
        week_num = current_date.isocalendar()[1]
        weekday = current_date.weekday()
        is_even_week = (week_num % 2 == 0)
        is_holiday = current_date.strftime("%Y-%m-%d") in HOLIDAYS_2026
        
        is_long_week = False
        if team_rule == "even" and is_even_week: is_long_week = True
        elif team_rule == "odd" and not is_even_week: is_long_week = True
            
        status = "Munka"
        if not is_long_week and (weekday == 0 or weekday >= 5): status = "SZABAD"
        
        hours = calculate_daily_hours(current_date, is_holiday, status) if status == "Munka" else 0
        total_hours += hours
        
        schedule_data.append({
            "Dátum": current_date.strftime("%Y-%m-%d"),
            "Nap": ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"][weekday],
            "Tervezett Státusz": status,
            "Tervezett Óra": hours
        })
        
    return pd.DataFrame(schedule_data), total_hours

# --- UI ---
st.set_page_config(page_title="Műszak és Fingera", layout="wide")
st.title("📅 Túlóra Egyenleg és Tervező")

col_y, col_m = st.columns(2)
with col_y:
    selected_year = st.number_input("Év", 2024, 2030, 2025)
with col_m:
    selected_month = st.selectbox("Hónap", range(1, 13), index=11)

tab1, tab2 = st.tabs(["👥 Havi Beosztás Terv", "📄 Fingera Egyenleg Ellenőrzés"])

with tab1:
    st.subheader("Csapat Terv")
    team = st.selectbox("Csapat", list(TEAMS_RULES.keys()))
    df_sched, total = generate_schedule(selected_year, selected_month, team)
    st.dataframe(df_sched, use_container_width=True, hide_index=True)

with tab2:
    st.subheader("Fingera Záróegyenleg Kinyerése")
    uploaded_file = st.file_uploader("Töltsd fel a Fingera PDF exportot", type=['pdf'])
    
    col_p1, col_p2 = st.columns(2)
    with col_p1:
        person_code = st.selectbox("Dolgozó kiválasztása:", list(PEOPLE_DATA.keys()))
        person_info = PEOPLE_DATA[person_code]
        st.info(f"Keresett név: **{person_info['fingera_name']}**")
    
    if uploaded_file:
        with st.spinner('Keresés a PDF-ben...'):
            final_balance, raw_text, found = extract_fingera_balance(uploaded_file, person_info['fingera_name'])
        
        st.divider()
        
        if found:
            st.success(f"✅ Adatok megtalálva!")
            
            # KIJELZŐK
            m1, m2 = st.columns(2)
            
            m1.metric(
                label="Fingera Záróegyenleg (Eredeti)", 
                value=raw_text, 
                help="Prenášaný nadčas do nasledujúceho mesiaca"
            )
            
            m2.metric(
                label="Fingera Záróegyenleg (Decimális)", 
                value=f"{final_balance:+.2f} óra",
                delta_color="normal" if final_balance >= 0 else "inverse"
            )
            
            if final_balance < 0:
                st.error(f"⚠️ A következő hónapot {raw_text} mínusszal kezdi!")
            else:
                st.success(f"✅ A következő hónapot {raw_text} plusszal kezdi!")
                
        else:
            st.warning("⚠️ Nem találtam meg ezt az embert vagy a záróegyenleget a PDF-ben.")
