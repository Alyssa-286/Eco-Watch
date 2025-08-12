import streamlit as st
import requests
import smtplib
from email.message import EmailMessage
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from sklearn.preprocessing import normalize

# --- SETTINGS & CONFIG ---
API_TOKEN = "c0d4ef13975cee2f3bd2afa4cdd4a7c7ea23ccb6"
SENDER_EMAIL = "knupur730@gmail.com"
SENDER_PASSWORD = "xmrp wapx vpkb gntv"

THRESHOLDS = {
    "pm25": 25, "pm10": 50, "co": 10,
    "no2": 200, "so2": 20, "o3": 100
}

# --- Micro-optimization: Define static data once as a constant ---
TREND_DF = pd.DataFrame({
    "Day": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "PM2.5": [90, 95, 100, 98, 102, 99, 96]
})


# --- STYLING ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap');

/* --- Animations --- */
@keyframes fadeInUp {
    0% { opacity: 0; transform: translateY(20px); }
    100% { opacity: 1; transform: translateY(0); }
}
@keyframes pulse {
    0% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0.4); }
    70% { box-shadow: 0 0 0 15px rgba(255, 0, 0, 0); }
    100% { box-shadow: 0 0 0 0 rgba(255, 0, 0, 0); }
}
@keyframes float {
    0% {transform: translate(0, 0);}
    50% {transform: translate(-50px, -50px);}
    100% {transform: translate(0, 0);}
}
@keyframes bounceIn {
    0% { transform: scale(0.6); opacity: 0; }
    60% { transform: scale(1.2); opacity: 1; }
    100% { transform: scale(1); }
}

/* --- General Layout & Typography --- */
html, body, [class*="css"] {
    font-family: 'Poppins', sans-serif;
    background-image: url('https://i.imgur.com/Io5mQpQ.jpg');
    background-size: cover;
    background-position: center;
    background-attachment: fixed;
}
.eco-title {
    font-size: 64px;
    color: #001f33;
    font-weight: 700;
    text-align: center;
    padding: 20px;
    border-radius: 12px;
    background: linear-gradient(to right, #99ccff, #cce6ff);
    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.3);
    text-shadow: 2px 2px 10px rgba(0, 0, 0, 0.3);
    transition: all 0.5s ease-in-out;
    animation: fadeInUp 1s ease-out;
}
.eco-title:hover {
    transform: scale(1.05);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5);
}

/* --- Interactive Elements --- */
input[type="text"] {
    background: rgba(255, 255, 255, 0.8);
    border: 2px solid #0077b6;
    border-radius: 10px;
    padding: 10px;
    font-size: 16px;
    transition: transform 0.3s ease, box-shadow 0.3s ease;
    animation: fadeInUp 1.2s ease-out;
}
input[type="text"]:focus {
    box-shadow: 0px 0px 10px rgba(0, 119, 182, 0.8);
    transform: scale(1.05);
}

/* --- Component Styles --- */
.pollutant-card {
    background: linear-gradient(145deg, #e0f7fa, #ffffff);
    border-radius: 20px;
    padding: 20px;
    margin-bottom: 15px;
    box-shadow: 6px 6px 15px #d0dce6, -6px -6px 15px #ffffff;
    text-align: center;
    font-weight: bold;
    font-size: 20px;
    transition: transform 0.3s ease;
    animation: fadeInUp 0.8s ease-out;
}
.pollutant-card:hover {
    transform: scale(1.05);
}
.beacon {
    width: 15px;
    height: 15px;
    background-color: #ff0000;
    border-radius: 50%;
    animation: pulse 2s infinite;
    display: inline-block;
    vertical-align: middle;
    margin-left: 10px;
}
.fact-box {
    background-color: #e3f6ff;
    padding: 20px;
    border-radius: 16px;
    font-size: 18px;
    font-weight: 500;
    color: #00334d;
    box-shadow: 0 4px 14px rgba(0,0,0,0.15);
    position: relative;
    overflow: hidden;
    margin: 10px;
}
.fact-box::before {
    content: ""; position: absolute; top: -20px; left: -20px;
    width: 200%; height: 200%;
    background: radial-gradient(circle, rgba(173,216,230,0.25) 20%, transparent 70%);
    animation: float 15s linear infinite;
}
.did-you-know {
    animation: bounceIn 2s ease-in-out;
}
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---
@st.cache_data(show_spinner="Fetching latest data...")
def get_realtime_aqi(city_name):
    """Fetches real-time AQI data from the WAQI API."""
    url = f"https://api.waqi.info/feed/{city_name}/?token={API_TOKEN}"
    try:
        response = requests.get(url, timeout=10)
        return response.json()
    except requests.RequestException:
        return {"status": "error", "data": "Network connection failed."}

def send_alert_email(to_email, city, alerts):
    """Constructs and sends a high-pollution alert email."""
    subject = f"🌫️ ECOWatch Alert - High Pollution in {city.title()}"
    body = (
        "🚨HIGH ALERT! Immediate health risk detected:\n"
        "* Avoid outdoor activities\n* Use N95 masks if needed\n"
        "* Close windows & ventilators\n* Keep children and elderly safe\n\n"
        "Live pollutant levels:\n" + "\n".join(alerts)
    )
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        st.success("🚨 Alert email sent successfully!")
    except Exception as e:
        st.error(f"❌ Failed to send email: {e}")

def create_fingerprint_plot(composition):
    """Creates the bar chart for the pollution composition."""
    pollutants_to_plot = ['pm25', 'pm10', 'co', 'no2', 'so2', 'o3']
    df = pd.DataFrame({
        'Pollutant': [p.upper() for p in pollutants_to_plot],
        'Concentration': [composition.get(p, {'v': 0})['v'] for p in pollutants_to_plot]
    })
    fig = px.bar(df, x='Pollutant', y='Concentration', title='Pollution Composition Fingerprint',
                 color='Pollutant', height=400)
    return fig

def create_source_pie(composition):
    """Creates the pie chart for estimated pollution sources."""
    categories = ['Industrial (SO2)', 'Vehicular (NO2)', 'Combustion (CO)', 'Particulates (PM2.5)']
    values_raw = [
        composition.get('so2', {'v': 0})['v'], composition.get('no2', {'v': 0})['v'],
        composition.get('co', {'v': 0})['v'], composition.get('pm25', {'v': 0})['v']
    ]
    if sum(values_raw) == 0:
        values = [25, 25, 25, 25]
    else:
        values = normalize([values_raw])[0] * 100
    fig = go.Figure(data=[go.Pie(labels=categories, values=values, textinfo='label+percent',
                                 hoverinfo='label+value+percent', textfont=dict(size=14),
                                 marker=dict(colors=['#0077b6', '#ff9900', '#cc3333', '#666699']))])
    fig.update_layout(
        title=dict(text="Estimated Pollution Source Analysis", font=dict(size=22), y=0.9, x=0.5, xanchor='center', yanchor='top'),
        font=dict(size=16), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    return fig

# --- MAIN APP UI ---
st.markdown("<div class='eco-title'>🌿ECOWatch</div>", unsafe_allow_html=True)

city = st.text_input("Enter city name to monitor:", value="Bangalore")
user_email = st.text_input("Enter your email to receive high-pollution alerts:")

aqi_data = get_realtime_aqi(city) if city else None

tabs = st.tabs(["Live AQI Dashboard", "Pollution DNA Fingerprint"])

# --- TAB 1: Live AQI Dashboard ---
with tabs[0]:
    if aqi_data and aqi_data.get("status") == "ok":
        data = aqi_data["data"]
        aqi_value = data['aqi']
        
        # Determine the color and beacon based on AQI value
        if aqi_value <= 50:
            color, beacon_html = "#28a745", "" # Green
        elif aqi_value <= 100:
            color, beacon_html = "#ffc107", "" # Yellow
        else:
            color, beacon_html = "#dc3545", "<span class='beacon'></span>" # Red
            
        # Use st.markdown to render the HTML alert box correctly
        st.markdown(
            f"""
            <div style="background-color: {color}; color: white; padding: 1rem; border-radius: 0.5rem; font-size: 1.1rem; font-weight: bold;">
              Current AQI in {data.get('city', {}).get('name', city.title())}: {aqi_value} {beacon_html}
            </div>
            """,
            unsafe_allow_html=True
        )

        iaqi = data.get("iaqi", {})
        alerts = []
        st.subheader("📊 Live Pollutant Levels")
        cols = st.columns(3)
        pollutant_items = list(iaqi.items())
        for i, (pollutant, val) in enumerate(pollutant_items):
            concentration = val.get("v", "N/A")
            display_text = f"{concentration} µg/m³" if isinstance(concentration, (int, float)) else "N/A"
            with cols[i % 3]:
                st.markdown(f"<div class='pollutant-card'>{pollutant.upper()}<br>{display_text}</div>", unsafe_allow_html=True)
            if pollutant in THRESHOLDS and isinstance(concentration, (int, float)) and concentration > THRESHOLDS[pollutant]:
                alerts.append(f"{pollutant.upper()} is {concentration} µg/m³ (⚠ exceeds {THRESHOLDS[pollutant]})")

        if alerts and user_email:
            send_alert_email(user_email, city, alerts)
        
        st.subheader("📈 AQI Trend - Last 7 Days (Sample)")
        fig_trend = px.bar(TREND_DF, x="Day", y="PM2.5", title="PM2.5 Levels This Week", color_discrete_sequence=["#0077b6"])
        st.plotly_chart(fig_trend, use_container_width=True)

        st.subheader("🗺️ Live AQI Map")
        map_coords = data.get('city', {}).get('geo', [12.97, 77.59])
        st.markdown(f'<iframe width="100%" height="450px" src="https://waqi.info/map/?latlng={map_coords[0]},{map_coords[1]}&zoom=10" frameborder="0"></iframe>', unsafe_allow_html=True)

        st.subheader("🌬️ 3D Global Wind View")
        st.markdown('<iframe src="https://earth.nullschool.net/" width="100%" height="450px" style="border:none;"></iframe>', unsafe_allow_html=True)

        st.subheader("💡 Did You Know?")
        st.markdown("<div class='fact-box did-you-know'>Indoor air pollution is often 2 to 5 times worse than outdoor. Good ventilation is key to healthier indoor air!</div>", unsafe_allow_html=True)

    elif city:
        st.error(f"Could not fetch AQI data for '{city}'. Please check the name or your internet connection.")

# --- TAB 2: Pollution DNA Fingerprint ---
with tabs[1]:
    if aqi_data and aqi_data.get("status") == "ok":
        iaqi_data = aqi_data["data"].get("iaqi", {})
        st.plotly_chart(create_fingerprint_plot(iaqi_data), use_container_width=True)
        st.markdown("<hr>", unsafe_allow_html=True)
        st.plotly_chart(create_source_pie(iaqi_data), use_container_width=True)
    else:
        st.warning("Please enter a valid city on the 'Live AQI Dashboard' tab to view its Pollution DNA.")