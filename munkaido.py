import streamlit as st
import pandas as pd
import pdfplumber
import re
import unicodedata
import io
import datetime
import calendar

# --- GRAFIKON MOTOR VÉDELEM ---
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- FŐ CÍM ---
st.title("Műszak Navigátor 3.2 (Rövid Péntek - 5:50 kezdéssel)")

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
                matches = re.findall(r"Spolu\s*([+-]?\d+:\d+)", text)
                
                if matches:
                    values = [parse_time_str(m) for m in matches]
                    max_val = max(values)
                    
                    if code in data:
                        data[code] = max(data[code], max_val)
                    else:
                        data[code] = max_val
                    
    return data

def calculate_future_hours(year, month, start_day, team_name, is_short_friday=False):
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
            short_friday_len = (6 + 40/60) - 0.5 # 5:50 - 12:30 mínusz 30p szünet
            
            if is_holiday or weekday >= 5: 
                day_hours = round(weekend_len, 2)
            elif weekday == 4 and is_short_friday: 
                day_hours = round(short_friday_len, 2)
            else: 
                day_hours = round(weekday_len, 2)
                
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

# --- MAIN LOGIC ---
try:
    team_map = get_team_labels()
    
    col1, col2 = st.columns(2)
    with col1:
        selected_year = st.number_input("Év", 2024, 2030, 2026)
        current_month = datetime.date.today().month
        selected_month = st.selectbox("Hónap", range(1, 13), index=current_month - 1)
        
    with col2:
        selected_label = st.selectbox("Csapat", list(team_map.keys()))
        selected_team = team_map[selected_label]
        
    short_friday_enabled = st.checkbox(
        "✨ Rövidített Péntek (Munkavégzés 5:50 - 12:30)", 
        value=False, 
        help="Ha bekapcsolod, minden jövőbeli péntek 6.17 nettó munkaórával fog számolódni."
    )
        
    st.divider()
    
    with st.expander("📂 Fájlfeltöltés", expanded=True):
        f1 = st.file_uploader("1. Múlt havi (Zárt) PDF", type=['pdf'], key="b")
        f2 = st.file_uploader("2. Mai (Hóközi) PDF", type=['pdf'], key="c")
        cut_date = st.date_input("Mai dátum:", value=datetime.date.today())

    if f1 and f2:
        st.subheader("Eredmények")
        with st.spinner('Kalkuláció folyamatban...'):
            start_bal = get_start_balances(f1)
            curr_spolu = get_current_worked_hours(f2)
            
            results = []
            norma = get_monthly_obligation(selected_year, selected_month)
            
            for code, info in PEOPLE_DATA.items():
                brought = start_bal.get(code, 0.0)
                spolu_value = curr_spolu.get(code, 0.0)
                
                if spolu_value == 0:
                    worked_so_far = 0.0
                else:
                    worked_so_far = max(0.0, spolu_value - brought)
                
                fut = calculate_future_hours(selected_year, selected_month, cut_date.day + 1, info['team'], short_friday_enabled)
                
                if spolu_value == 0:
                     end = brought + fut - norma
                else:
                     end = spolu_value + fut - norma
                
                act = f"+{abs(end):.2f} óra!" if end < 0 else ""
                
                results.append({
                    "Név": info['fingera_name'],
                    "Hozott": brought, 
                    "Eddig": worked_so_far,
                    "Jövő": fut, 
                    "Norma": norma, 
                    "Várható Záró": end, 
                    "Teendő": act
                })
            
            df = pd.DataFrame(results).round(2)
            
            fig, ax = plt.subplots(figsize=(8, 4))
            cols = ['green' if x >= 0 else 'red' for x in df['Várható Záró']]
            bars = ax.bar(df['Név'], df['Várható Záró'], color=cols)
            ax.axhline(0, color='black')
            plt.xticks(rotation=45, ha='right')
            ax.bar_label(bars, fmt='%.2f')
            
            st.pyplot(fig)
            st.dataframe(df)
            
            excel = generate_excel_report(df, fig)
            st.download_button("📥 Excel Letöltése", excel, "riport.xlsx")
            
            plt.close(fig)

except Exception as e:
    st.error(f"Hiba: {e}")
