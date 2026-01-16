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

# --- FÜGGVÉNYEK ---
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
    # BIZTONSÁGI LÉPÉS: Visszatekerjük a fájlt az elejére
    pdf_file.seek(0)
    data = {}
    norm_name_to_code = {normalize_text(v['fingera_name']): k for k, v in PEOPLE_DATA.items()}
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            text_norm = normalize_text(text)
            found_codes = [code for norm, code in norm_name_to_code.items() if norm in text_norm]
            for code in found_codes:
                match = re.search(r"Prenášaný nadčas do nasledujúceho mesiaca\s*([+-]?\d+:\d+)", text)
                if match: data[code] = parse_time_str(match.group(1))
    return data

def get_current_worked_hours(pdf_file):
    # BIZTONSÁGI LÉPÉS: Visszatekerjük a fájlt az elejére
    pdf_file.seek(0)
    data = {}
    norm_name_to_code = {normalize_text(v['fingera_name']): k for k, v in PEOPLE_DATA.items()}
    
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text: continue
            text_norm = normalize_text(text)
            found_codes = [code for norm, code in norm_name_to_code.items() if norm in text_norm]
            for code in found_codes:
                match = re.search(r"Čas v práci \(netto\)\s*(\d+:\d+)", text)
                if match: data[code] = parse_time_str(match.group(1))
    return data

def calculate_future_hours(year, month, start_day, team_name):
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
    num_days = calendar.monthrange(year, month)[1]
    workdays = 0
    for day in range(1, num_days + 1):
        d = datetime.date(year, month, day)
        if d.weekday() < 5 and d.strftime("%Y-%m-%d") not in HOLIDAYS_2026:
            workdays += 1
    return workdays * 8

def generate_excel_report(df, fig_chart):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        sheet_name = 'Kimutatás'
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        num_fmt = workbook.add_format({'num_format': '0.00'})
        worksheet.set_column('A:A', 20) 
        worksheet.set_column('B:F', 12, num_fmt) 
        worksheet.set_column('G:G', 30) 
        
        red_format = workbook.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE'})
        green_format = workbook.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE'})
        
        worksheet.conditional_format('F2:F100', {'type': 'cell', 'criteria': '<', 'value': 0, 'format': red_format})
        worksheet.conditional_format('F2:F100', {'type': 'cell', 'criteria': '>=', 'value': 0, 'format': green_format})

        img_data = io.BytesIO()
        fig_chart.savefig(img_data, format='png', bbox_inches='tight', dpi=100)
        img_data.seek(0)
        worksheet.insert_image('I2', 'grafikon.png', {'image_data': img_data})
        
    output.seek(0)
    return output

def get_team_labels():
    labels = {}
    for team_key in TEAMS_RULES.keys():
        members = [code for code, data in PEOPLE_DATA.items() if data['team'] == team_key]
        members_str = ", ".join(members)
        label = f"{team_key} ({members_str})"
        labels[label] = team_key 
    return labels

# --- UI FELÉPÍTÉS ---
st.set_page_config(page_title="Műszak Navigátor", layout="wide", page_icon="⏱️")

st.title("⏱️ Műszak és Túlóra Navigátor")

try:
    team_map = get_team_labels()
    team_options = list(team_map.keys())

    col_params = st.columns(4)
    with col_params[0]:
        selected_year = st.number_input("Év", 2024, 2030, 2026)
    with col_params[1]:
        selected_month = st.selectbox("Hónap", range(1, 13), index=0)
    with col_params[2]:
        selected_label = st.selectbox("Csapat (Tervhez)", team_options)
        selected_team = team_map[selected_label]
    with col_params[3]:
        ideal_hours = calculate_future_hours(selected_year, selected_month, 1, selected_team)
        norma = get_monthly_obligation(selected_year, selected_month)
        st.metric("Havi Terv / Norma", f"{ideal_hours:.2f} / {norma} óra")

    st.divider()

    with st.expander("📂 Fingera Adatok Betöltése (Kattints a lenyitáshoz)", expanded=True):
        col_f1, col_f2, col_date = st.columns([1, 1, 1])
        with col_f1:
            file_base = st.file_uploader("1. Múlt havi PDF (Lezárt)", type=['pdf'], key="base")
        with col_f2:
            file_current = st.file_uploader("2. Mai PDF (Hóközi)", type=['pdf'], key="curr")
        with col_date:
            today = datetime.date.today()
            def_date = today if (today.year == selected_year and today.month == selected_month) else datetime.date(selected_year, selected_month, 15)
            cut_off_date = st.date_input("Mai dátum (vagy adat állapota):", value=def_date)

    if file_base and file_current:
        st.subheader(f"📊 Előrejelzés ({selected_year}.{selected_month:02d}.)")
        
        # BIZTONSÁGI BLOKK: Ha hiba van a fájlokkal, itt elkapjuk
        try:
            with st.spinner('Adatok összefésülése...'):
                start_balances = get_start_balances(file_base)
                worked_current = get_current_worked_hours(file_current)
                
                # Ha üresek az adatok, szólunk
                if not start_balances and not worked_current:
                    st.warning("⚠️ Nem találtam adatokat a PDF-ekben. Biztos jó fájlokat töltöttél fel?")
                else:
                    monthly_obligation = get_monthly_obligation(selected_year, selected_month)
                    
                    results = []
                    for code, person_info in PEOPLE_DATA.items():
                        brought = start_balances.get(code, 0.0)
                        worked = worked_current.get(code, 0.0)
                        future_plan = calculate_future_hours(selected_year, selected_month, cut_off_date.day + 1, person_info['team'])
                        end_balance = brought + worked + future_plan - monthly_obligation
                        
                        action = "Nincs teendő"
                        if end_balance < 0:
                            action = f"+{abs(end_balance):.2f} óra túlóra!"
                        
                        results.append({
                            "Név": person_info['fingera_name'],
                            "Hozott": brought,
                            "Eddig": worked,
                            "Jövő": future_plan,
                            "Norma": monthly_obligation,
                            "Várható Záró": end_balance,
                            "Teendő": action
                        })
                        
                    df_res = pd.DataFrame(results).round(2)
                    
                    # Grafikon
                    fig, ax = plt.subplots(figsize=(8, 4))
                    colors = ['#28a745' if x >= 0 else '#dc3545' for x in df_res['Várható Záró']]
                    bars = ax.bar(df_res['Név'], df_res['Várható Záró'], color=colors)
                    ax.axhline(0, color='black', linewidth=0.8)
                    plt.xticks(rotation=45, ha='right', fontsize=9)
                    ax.set_title("Várható Záróegyenleg", fontsize=10)
                    for bar in bars:
                        yval = bar.get_height()
                        ax.text(bar.get_x() + bar.get_width()/2, yval, f"{yval:.2f}", 
                                ha='center', va='bottom' if yval>0 else 'top', fontsize=8, fontweight='bold')
                    
                    col_chart, col_table = st.columns([1, 1.5])
                    with col_chart:
                        st.pyplot(fig)
                        # FONTOS: Memória felszabadítás
                        plt.close(fig)
                        
                    with col_table:
                        def highlight_danger(row):
                            if row['Várható Záró'] < 0:
                                return ['background-color: #ffe6e6; color: #b30000'] * len(row)
                            return [''] * len(row)

                        st.dataframe(
                            df_res.style.apply(highlight_danger, axis=1).format("{:.2f}", subset=["Hozott", "Eddig", "Jövő", "Norma", "Várható Záró"]),
                            use_container_width=True,
                            height=350
                        )

                    st.divider()
                    
                    # Újra létrehozzuk a grafikont a mentéshez (mert a plt.close bezárta)
                    fig_save, ax_save = plt.subplots(figsize=(10, 5))
                    bars_save = ax_save.bar(df_res['Név'], df_res['Várható Záró'], color=colors)
                    ax_save.axhline(0, color='black')
                    plt.xticks(rotation=45, ha='right')
                    for bar in bars_save:
                         ax_save.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{bar.get_height():.2f}", ha='center')

                    excel_data = generate_excel_report(df_res, fig_save)
                    plt.close(fig_save) # Ezt is bezárjuk
                    
                    st.download_button(
                        label="📥 Teljes Kimutatás Letöltése (Excel + Grafikon)",
                        data=excel_data,
                        file_name=f'vezeto_riport_{selected_year}_{selected_month}.xlsx',
                        mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )

                    if not df_res[df_res['Várható Záró'] < 0].empty:
                        st.error(f"⚠️ **Figyelem!** {len(df_res[df_res['Várható Záró'] < 0])} dolgozó mínuszban végezhet!")
                    else:
                        st.success("✅ Mindenki biztonságban van.")
        
        except Exception as e:
            st.error(f"❌ Hiba történt a feldolgozás során: {e}")
            st.info("Próbáld meg frissíteni az oldalt, vagy ellenőrizd a PDF fájlokat.")

except Exception as e:
    st.error(f"Kritikus hiba az alkalmazás indításakor: {e}")
