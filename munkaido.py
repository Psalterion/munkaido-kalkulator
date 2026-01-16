import streamlit as st
import pandas as pd
import matplotlib
matplotlib.use('Agg') # A biztonsági kapcsoló
import matplotlib.pyplot as plt

st.title("Könyvtár Teszt")
st.write(f"Pandas verzió: {pd.__version__}")
st.write(f"Matplotlib verzió: {matplotlib.__version__}")

# Próbáljunk rajzolni valamit memóriában
try:
    fig, ax = plt.subplots()
    ax.plot([1, 2, 3], [1, 2, 3])
    st.pyplot(fig)
    st.success("A grafikonrajzoló motor is működik!")
except Exception as e:
    st.error(f"Hiba a grafikonnal: {e}")
