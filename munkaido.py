import streamlit as st
import pandas as pd
import datetime
import calendar
import pdfplumber
import re
import unicodedata
import matplotlib.pyplot as plt
import io

# --- KONFIGURÁCIÓ ---
TEAMS_RULES = {
    "1. Csapat": {"weekend_work": "even"},
    "2. Csapat": {"weekend_work": "odd"}
}

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
    if not text: return ""
    return ''.join(c for c in unicodedata.normalize('NFD', text)
                  if unicodedata.category(c) != 'Mn').lower()

def parse_time_str(time_str):
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

def get_start_balances(pdf_file):
    """Csak a NYITÓ egyenlegeket szedi ki a lezárt PDF-ből."""
    data = {}
    norm_name_to_code = {normalize_text(v['fingera_name']): k for k, v in PEOPLE_DATA.items()}
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            text_norm = normalize_text(text)
            
            # Keresés
            found_codes = [code for norm, code in norm_name_to_code.items() if norm in text_norm]
            
            for code in found_codes:
                # Prenášaný nadčas do nasledujúceho mesiaca (Ez volt a záró, ami most nyitó)
                match = re.search(r"Prenášaný nadčas do nasledujúceho mesiaca\s*([+-]?\d+:\d+)", text)
                if match:
                    data[code] = parse_time_str(match.group(1))
    return data

def get_current_worked_hours(pdf_file):
    """Csak a TÉNYLEGESEN LEDOLGOZOTT időt szedi ki a mostani PDF-ből."""
    data = {}
    norm_name_to_code = {normalize_text(v['fingera_name']): k for k, v in PEOPLE_DATA.items()}
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            text_norm = normalize_text(text)
            
            found_codes = [code for norm, code in norm_name_to_code.items() if norm in text_norm]
            
            for code in found_codes:
                # Čas v práci (netto)
                match = re.search(r"Čas v práci \(netto\)\s*(\d+:\d+)", text)
                if match:
                    data[code] = parse_time_str(match.group(1))
    return data

def calculate_future_hours(year, month, start_day, team_name):
    """Kiszámolja a TERVEZETT munkaórákat a hónap HÁTRALÉVŐ részére."""
    team_rule = TEAMS_RULES[team_name]["weekend_work"]
    num_days = calendar.monthrange(year, month)[1]
    future_hours = 0
    
    if start_day > num_days: return 0
        
    for day in range(start_day, num_days + 1):
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
        
        day_hours = 0
        if status == "Munka":
            weekday_len = (7 + 40/60) - 0.5
            weekend_len = (6 + 10/60) - 0.5
            if is_holiday or weekday >= 5: day_hours = round(weekend_len, 2)
            else: day_hours = round(weekday_len, 2)
            
        future_hours += day_hours
    return future_hours

def get_monthly_obligation(year, month):
    """Kiszámolja a havi kötelezőt."""
    num_days = calendar.monthrange(year, month)[1]
    workdays = 0
    for day in range(1, num_days + 1):
        d = datetime.date(year, month, day)
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in HOLIDAYS_2026:
            workdays += 1
    return workdays * 8

# --- UI ---
st.set_page_config(page_title="Műszak Navigátor", layout="wide", page_icon="🧭")
st.title("🧭 Műszak Navigátor: Két Fájlos Rendszer")

col_y, col_m = st.columns(2)
with col_y:
    selected_year = st.number_input("Év", 2024, 2030, 2026)
with col_m:
    selected_month = st.selectbox("Hónap", range(1, 13), index=0)

tab1, tab2 = st.tabs(["📅 Havi Ideális Terv", "🚨 Hóközi Navigátor (Dual File)"])

# --- TAB 1 ---
with tab1:
    st.info("Ideális állapot (ha mindenki végigdolgozza a hónapot).")
    team_view = st.selectbox("Csapat", list(TEAMS_RULES.keys()))
    planned = calculate_future_hours(selected_year, selected_month, 1, team_view)
    obligation = get_monthly_obligation(selected_year, selected_month)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Havi Kötelező", f"{obligation} óra")
    c2.metric("Tervezett", f"{planned:.2f} óra")
    c3.metric("Egyenleg", f"{planned - obligation:.2f} óra")

# --- TAB 2: A MEGOLDÁS ---
with tab2:
    st.subheader("Hóközi Ellenőrzés: Múlt + Jelen = Jövő")
    st.markdown("A pontos számoláshoz **két** fájlra van szükség:")
    
    col_file1, col_file2 = st.columns(2)
    
    # 1. Fájl: Múlt
    with col_file1:
        st.markdown("### 1. BÁZIS (Múlt hó)")
        file_base = st.file_uploader("Töltsd fel a LEZÁRT múlt havi PDF-et", type=['pdf'], key="base")
        st.caption("Ebből vesszük ki a HOZOTT egyenleget.")
        
    # 2. Fájl: Jelen
    with col_file2:
        st.markdown("### 2. AKTUÁLIS (Mai)")
        file_current = st.file_uploader("Töltsd fel a MAI hóközi PDF-et", type=['pdf'], key="curr")
        st.caption("Ebből vesszük ki az EDDIG ledolgozott időt.")

    st.divider()
    
    # Dátum választó
    today = datetime.date.today()
    default_date = today if (today.year == selected_year and today.month == selected_month) else datetime.date(selected_year, selected_month, 15)
    cut_off_date = st.date_input("Meddig tartalmaz adatokat a 2. fájl?", value=default_date)

    if file_base and file_current:
        with st.spinner('Összefésülés és számolás...'):
            # Adatok kinyerése külön-külön
            start_balances = get_start_balances(file_base)
            worked_current = get_current_worked_hours(file_current)
            
            results = []
            monthly_obligation = get_monthly_obligation(selected_year, selected_month)
            
            for code, person_info in PEOPLE_DATA.items():
                # Összefésülés
                brought = start_balances.get(code, 0.0)
                worked = worked_current.get(code, 0.0)
                
                # Jövő számítása
                future_plan = calculate_future_hours(selected_year, selected_month, cut_off_date.day + 1, person_info['team'])
                
                # Végeredmény
                end_balance = brought + worked + future_plan - monthly_obligation
                
                # Akció
                status_txt = "OK"
                action = ""
                if end_balance < 0:
                    status_txt = "BAJ"
                    missing = abs(end_balance)
                    action = f"+{missing:.1f} óra túlóra kell!"
                
                results.append({
                    "Név": person_info['fingera_name'],
                    "Hozott (Múlt)": brought,
                    "Eddig (Tény)": worked,
                    "Hátralévő (Terv)": future_plan,
                    "Havi Norma": monthly_obligation,
                    "Várható Záró": end_balance,
                    "Teendő": action
                })
            
            df_res = pd.DataFrame(results)
            
            # Grafikon
            st.subheader("📊 Várható Záróegyenleg")
            fig, ax = plt.subplots(figsize=(10, 4))
            colors = ['#28a745' if x >= 0 else '#dc3545' for x in df_res['Várható Záró']]
            bars = ax.bar(df_res['Név'], df_res['Várható Záró'], color=colors)
            ax.axhline(0, color='black', linewidth=1)
            plt.xticks(rotation=45, ha='right')
            
            for bar in bars:
                yval = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2, yval, f"{yval:.1f}", ha='center', va='bottom' if yval>0 else 'top', fontweight='bold')
            st.pyplot(fig)
            
            # Táblázat
            st.subheader("📋 Részletes Teendők")
            def highlight_row(row):
                return ['background-color: #f8d7da; color: #721c24'] * len(row) if row['Várható Záró'] < 0 else [''] * len(row)

            st.dataframe(
                df_res.style.apply(highlight_row, axis=1).format("{:.1f}", subset=["Hozott (Múlt)", "Eddig (Tény)", "Hátralévő (Terv)", "Havi Norma", "Várható Záró"]),
                use_container_width=True
            )
            
            if not df_res[df_res['Várható Záró'] < 0].empty:
                st.error("⚠️ Beavatkozás szükséges! Lásd a piros sorokat.")
            else:
                st.success("✅ Mindenki biztonságban van.")
                
    elif not file_base and not file_current:
        st.info("Kérlek töltsd fel mindkét fájlt az elemzéshez!")
    else:
        st.warning("Még hiányzik az egyik fájl!")
