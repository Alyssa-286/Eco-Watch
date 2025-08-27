import streamlit as st
import requests
import smtplib
from email.message import EmailMessage
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from sklearn.preprocessing import normalize
import os
from dotenv import load_dotenv

# --- CONFIGURATION ---
load_dotenv()
API_TOKEN = os.getenv("API_TOKEN")
SENDER_EMAIL = os.getenv("SENDER_EMAIL")
SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")

THRESHOLDS = {"pm25": 25, "pm10": 50, "co": 10, "no2": 200, "so2": 20, "o3": 100}

# --- STYLING ---
# NEW: Function to load CSS from an external file
def load_css(file_name):
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.error(f"CSS file '{file_name}' not found. Please create it.")

# --- DATA & API HELPERS ---
@st.cache_data(show_spinner="Fetching latest data...")
def get_realtime_aqi(city_name):
    """Fetches real-time AQI data from the WAQI API."""
    if not API_TOKEN: return {"status": "error", "data": "API_TOKEN not configured."}
    url = f"https://api.waqi.info/feed/{city_name}/?token={API_TOKEN}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"status": "error", "data": f"Network connection failed: {e}"}

def generate_weekly_trend_data(city_name):
    """Generates consistent but random-looking weekly data based on the city name."""
    np.random.seed(sum(ord(c) for c in city_name))
    base_aqi = np.random.randint(40, 150)
    trend = base_aqi + np.random.randint(-15, 15, size=7).cumsum()
    return pd.DataFrame({"Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], "PM2.5": trend})

# --- UI & PLOTTING FUNCTIONS ---
def display_dashboard(aqi_data, city, user_email):
    """Renders the main Live AQI Dashboard tab."""
    data = aqi_data["data"]
    aqi_value = data.get('aqi', 0)
    
    if aqi_value <= 50: status_color, beacon = "#28a745", ""
    elif aqi_value <= 100: status_color, beacon = "#ffc107", ""
    else: status_color, beacon = "#dc3545", "<span class='beacon'></span>"
        
    st.markdown(
        f"""<div style="background-color: {status_color}; color: white; padding: 1rem; border-radius: 0.5rem; font-size: 1.1rem; font-weight: bold;">
        Current AQI in {data.get('city', {}).get('name', city.title())}: {aqi_value} {beacon}</div>""",
        unsafe_allow_html=True
    )

    st.subheader("📊 Live Pollutant Levels")
    cols = st.columns(3)
    alerts = []
    iaqi = data.get("iaqi", {})
    for i, (pollutant, val) in enumerate(iaqi.items()):
        concentration = val.get("v", "N/A")
        display_text = f"{concentration} µg/m³" if isinstance(concentration, (int, float)) else "N/A"
        cols[i % 3].markdown(f"<div class='pollutant-card'>{pollutant.upper()}<br>{display_text}</div>", unsafe_allow_html=True)
        if pollutant in THRESHOLDS and isinstance(concentration, (int, float)) and concentration > THRESHOLDS[pollutant]:
            alerts.append(f"{pollutant.upper()} is {concentration} µg/m³ (⚠ exceeds {THRESHOLDS[pollutant]})")

    if alerts and user_email: send_alert_email(user_email, city, alerts)
    
    trend_df = generate_weekly_trend_data(city)
    fig_trend = px.bar(trend_df, x="Day", y="PM2.5", title=f"Sample PM2.5 Trend for {city.title()}", color_discrete_sequence=["#0077b6"])
    st.plotly_chart(fig_trend, use_container_width=True)

    st.subheader("🗺️ Live AQI Map")
    map_coords = data.get('city', {}).get('geo', [12.97, 77.59])
    st.markdown(f'<iframe width="100%" height="450px" src="https://waqi.info/map/?latlng={map_coords[0]},{map_coords[1]}&zoom=10" frameborder="0"></iframe>', unsafe_allow_html=True)

    st.subheader("🌬️ 3D Global Wind View")
    st.markdown('<iframe src="https://earth.nullschool.net/" width="100%" height="450px" style="border:none;"></iframe>', unsafe_allow_html=True)
    st.markdown("<div class='fact-box did-you-know'>Indoor air pollution is often 2 to 5 times worse than outdoor. Good ventilation is key to healthier indoor air!</div>", unsafe_allow_html=True)

def display_pollution_dna(aqi_data):
    """Renders the Pollution DNA Fingerprint tab."""
    iaqi_data = aqi_data["data"].get("iaqi", {})
    
    pollutants = ['pm25', 'pm10', 'co', 'no2', 'so2', 'o3']
    concentrations = [iaqi_data.get(p, {'v': 0})['v'] for p in pollutants]
    df_fingerprint = pd.DataFrame({'Pollutant': [p.upper() for p in pollutants], 'Concentration': concentrations})
    fig_fingerprint = px.bar(df_fingerprint, x='Pollutant', y='Concentration', title='Pollution Composition Fingerprint', color='Pollutant', height=400)
    st.plotly_chart(fig_fingerprint, use_container_width=True)
    
    st.markdown("<hr>", unsafe_allow_html=True)

    categories = ['Industrial (SO2)', 'Vehicular (NO2)', 'Combustion (CO)', 'Particulates (PM2.5)']
    values_raw = np.array([iaqi_data.get(p, {'v': 0})['v'] for p in ['so2', 'no2', 'co', 'pm25']])
    values = normalize([values_raw])[0] * 100 if values_raw.sum() > 0 else [25, 25, 25, 25]
    fig_pie = go.Figure(data=[go.Pie(labels=categories, values=values, textinfo='label+percent', hoverinfo='label+value+percent', marker=dict(colors=['#0077b6', '#ff9900', '#cc3333', '#666699']))])
    fig_pie.update_layout(title="Estimated Pollution Source Analysis", paper_bgcolor='rgba(0,0,0,0)', legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
    st.plotly_chart(fig_pie, use_container_width=True)

def send_alert_email(to_email, city, alerts):
    """Constructs and sends a high-pollution alert email."""
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        st.warning("Email credentials not configured. Cannot send alert.")
        return
    msg = EmailMessage()
    msg["Subject"] = f"🌫️ ECOWatch Alert - High Pollution in {city.title()}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg.set_content(f"🚨HIGH ALERT! Immediate health risk detected in {city.title()}:\n\n" + "\n".join(alerts))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        st.success("🚨 Alert email sent successfully!")
    except Exception as e:
        st.error(f"❌ Failed to send email: {e}")

# --- MAIN APP ---
st.set_page_config(page_title="ECOWatch", page_icon="🌿", layout="wide")
load_css("style.css") # This line loads your external CSS file

st.markdown("<div class='eco-title'>🌿ECOWatch</div>", unsafe_allow_html=True)
city = st.text_input("Enter city name to monitor:", value="Bangalore")
user_email = st.text_input("Enter your email to receive high-pollution alerts:")

if city:
    aqi_data = get_realtime_aqi(city)
    if aqi_data and aqi_data.get("status") == "ok":
        tab1, tab2 = st.tabs(["Live AQI Dashboard", "Pollution DNA Fingerprint"])
        with tab1:
            display_dashboard(aqi_data, city, user_email)
        with tab2:
            display_pollution_dna(aqi_data)
    else:
        error_message = aqi_data.get("data", "Please check the name or your internet connection.")
        st.error(f"Could not fetch AQI data for '{city}'. Reason: {error_message}")