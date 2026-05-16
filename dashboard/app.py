import streamlit as st
import pandas as pd
import numpy as np
from engine import Engine

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Algeria Air Quality",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATA LAYER ---
@st.cache_resource
def load_data():
    """Initializes the engine and loads static data."""
    engine = Engine()
    return engine

engine = load_data()

# Sidebar Setup
with st.sidebar:
    st.title("Algeria Air Quality")
    st.markdown("---")
    
    # ERA5-Land data typically has a latency of 2-3 months, so we default to 90 days ago
    default_date = pd.to_datetime('today') - pd.DateOffset(days=90)
    date = st.date_input("Select Date", value=default_date, max_value=pd.to_datetime('today'))

    
    # Wilaya filter
    wilayas = ["All"] + engine.get_wilayas()
    selected_wilaya = st.selectbox("Select Wilaya", wilayas, index=0)
    
    st.markdown("---")
    st.subheader("About")
    st.info(
        "This dashboard visualizes PM2.5 air quality predictions across Algerian Wilayas."
    )
    
    if st.button("Refresh Data", type="primary"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

# --- MAIN LAYOUT ---
st.markdown(f"#### Monitoring PM2.5 Levels for **{date.strftime('%Y-%m-%d')}**")

# --- MAP VISUALIZATION ---
with st.spinner("Generating air quality map..."):
    try:
        fig = engine.initialize_map(date, selected_wilaya)
        st.plotly_chart(fig, width='stretch', height=510)
    except Exception as e:
        st.error(f"Error generating map: {e}")

#  Display Raw Data Table
if st.checkbox("Show Raw Prediction Data"):
    with st.expander("Prediction Data", expanded=False):
        st.dataframe(engine.predicted_data)
