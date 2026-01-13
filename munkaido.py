import streamlit as st
import pandas as pd
import datetime
import calendar

# --- KONFIGURÁCIÓ ÉS ÁLLANDÓK ---
# Csapatok definíciója
TEAMS = {
    "1. Csapat (VIS, RE, MÁ, JK, TK)": {"weekend_work": "even"}, # Páros héten dolgozik hétvégén
    "2. Csapat (VIN, VT, VCS, ME)":   {"weekend_work": "odd"}  # Páratlan héten dolgozik hétvégén
}

# Ünnepnapok (Szlovákia/Magyarország vegyes példa, bővíthető)
HOLIDAYS_2026 = [
    "2026-01-01", "2026-01-06", "2026-04-03", "2026-04-06", 
    "2026-05-01", "2026-05-08", "2026-07-05", "2026-08-29", 
    "2026-09-01", "2026-09-15", "2026-11-01", "2026-11-17", "2026-12-24", "2026-12-25", "2026-12-26"
]

def calculate_hours(date_obj, is_holiday, shift_type):
    """Kiszámolja a nettó munkaórát a szabályok alapján."""
    # Nettó idők (Bruttó - 30 perc szünet)
    weekday_hours = (7 + 40/60) - 0.5  # 5:50-13:30 = 7h 40m
    weekend_hours = (6 + 10/60) - 0.5  # 5:50-12:00 = 6h 10m
    
    if shift_type == "SZABAD":
        return 0.0
    
    # Ha ünnepnap VAGY hétvége -> Rövid műszak
    if is_holiday or date_obj.weekday() >= 5: # 5=Szombat, 6=Vasárnap
        return round(weekend_hours, 2)
    else:
        return round(weekday_hours, 2)

def generate_schedule(year, month, team_name):
    team_rule = TEAMS[team_name]["weekend_work"]
    
    num_days = calendar.monthrange(year, month)[1]
    schedule_data = []
    
    total_hours = 0
    
    for day in range(1, num_days + 1):
        current_date = datetime.date(year, month, day)
        week_num = current_date.isocalendar()[1]
        weekday = current_date.weekday() # 0=Hétfő, 6=Vasárnap
        is_even_week = (week_num % 2 == 0)
        
        # Ünnepnap ellenőrzés
        is_holiday = current_date.strftime("%Y-%m-%d") in HOLIDAYS_2026
        
        # CIKLUS LOGIKA
        # 1. Határozzuk meg, hogy ez a hét "Hosszú" (hétvégi munka) vagy "Rövid" (szabad hétvége) a csapatnak
        is_long_week = False
        if team_rule == "even" and is_even_week:
            is_long_week = True
        elif team_rule == "odd" and not is_even_week:
            is_long_week = True
            
        # 2. Napi státusz meghatározása
        status = "Munka"
        shift_note = "Normál"
        
        if is_long_week:
            # Hosszú hét: H-P munka, Szo-V munka
            if is_holiday: shift_note = "Ünnepi műszak"
            elif weekday >= 5: shift_note = "Hétvégi műszak"
        else:
            # Rövid hét: Hétfő SZABAD, Szo-V SZABAD
            if weekday == 0: # Hétfő
                status = "SZABAD"
                shift_note = "Pihenőnap (Hétfő)"
            elif weekday >= 5: # Hétvége
                status = "SZABAD"
                shift_note = "Pihenőnap (Hétvége)"
            elif is_holiday:
                 # Ha ünnep hétköznapra esik a rövid héten -> Ünnepi munka
                 shift_note = "Ünnepi műszak"
        
        # Óraszám számítás
        hours = calculate_hours(current_date, is_holiday, status) if status == "Munka" else 0
        total_hours += hours
        
        # Magyar nap név
        day_name = ["Hétfő", "Kedd", "Szerda", "Csütörtök", "Péntek", "Szombat", "Vasárnap"][weekday]
        
        schedule_data.append({
            "Dátum": current_date.strftime("%Y-%m-%d"),
            "Nap": day_name,
            "Hét": f"{week_num}. ({'Páros' if is_even_week else 'Páratlan'})",
            "Státusz": status,
            "Megjegyzés": shift_note,
            "Óra": hours
        })
        
    return pd.DataFrame(schedule_data), total_hours

# --- STREAMLIT UI ---
st.title("📅 Prediktív Műszak és Bérszámfejtés Támogató")
st.write("Válassz csapatot és hónapot a várható munkaórák kiszámításához.")

col1, col2, col3 = st.columns(3)
with col1:
    selected_team = st.selectbox("Válassz Csapatot:", list(TEAMS.keys()))
with col2:
    selected_year = st.number_input("Év", min_value=2025, max_value=2030, value=2026)
with col3:
    selected_month = st.selectbox("Hónap", range(1, 13), index=0)

# Számítás
df_schedule, total_sum = generate_schedule(selected_year, selected_month, selected_team)

# --- EREDMÉNYEK MEGJELENÍTÉSE ---
st.divider()

# KPI kártyák
kpi1, kpi2, kpi3 = st.columns(3)
kpi1.metric("Összes munkaóra (becsült)", f"{total_sum:.2f} óra")
kpi2.metric("Munkanapok száma", f"{len(df_schedule[df_schedule['Státusz']=='Munka'])} nap")
kpi3.metric("Szabadnapok száma", f"{len(df_schedule[df_schedule['Státusz']=='SZABAD'])} nap")

# Log Sheet (A te kérésed szerint)
st.subheader("Részletes Log Sheet")
st.dataframe(
    df_schedule,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Óra": st.column_config.NumberColumn("Munkaóra", format="%.2f"),
        "Státusz": st.column_config.TextColumn("Állapot", width="small"),
    }
)

# Letöltés gomb
csv = df_schedule.to_csv(index=False).encode('utf-8')
st.download_button(
    label="Log Sheet Letöltése (CSV)",
    data=csv,
    file_name=f'munkaido_terv_{selected_team[:5]}_{selected_year}_{selected_month}.csv',
    mime='text/csv',
)
