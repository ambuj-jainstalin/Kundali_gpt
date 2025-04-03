from datetime import datetime,timedelta
import os
import time
import streamlit as st
from dotenv import load_dotenv
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_google_genai import GoogleGenerativeAI
import swisseph as swe
import json
import requests
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle
import plotly.graph_objects as go
import plotly
from matplotlib.patches import Polygon

load_dotenv()

# ✅ Set Ephemeris Path
swe.set_ephe_path("/path/to/ephemeris/")

# ✅ Initialize Session State
if "user_details" not in st.session_state:
    st.session_state.user_details = None
if "astro_data" not in st.session_state:
    st.session_state.astro_data = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory()
if "first_message_sent" not in st.session_state:
    st.session_state.first_message_sent = False

llm = GoogleGenerativeAI(
        model="gemini-2.0-flash",
        api_key=os.getenv("GOOGLE_API_KEY"),
        stream=True
    )
if "conversation" not in st.session_state:
    system_prompt="""You are an AI Astrologer. Follow these guidelines while responding:
    1. Focus Only on Astrology: Do not discuss topics unrelated to astrology. If a user asks, politely steer the conversation back.
    2. No Unnecessary Preface: Directly provide insights without generic phrases like "As an AI, I can help you with..." or "based on information provided"
    3. Use Astrological Calculations: Ensure accurate calculations for Kundali, planetary positions, houses, and transits.
    4. Provide Specific Predictions: Use Vedic astrology principles to give personalized readings.
    5. No Repetitive or Vague Responses: Avoid over-explaining concepts the user already knows.
    6. Follow Traditional and Modern Astrology: Use a blend of classical Vedic astrology and computational analysis where required.
    7. Handle Birth Details Carefully: Always refer to the user’s DOB, time, and place before making predictions.
    8. Be Concise Yet Informative: Provide detailed yet digestible responses, avoiding unnecessary fluff.
    9. Use Simple Language: Make astrology accessible to all users.
    10. Do Not Generate Random Predictions: Base insights strictly on astrological data.
    11. First Provide Snapsot like , Birth Details, Sun Sign, Moon Sign, Nakshatra, Day of Birth, Yoni etcs"""
    st.session_state.memory.chat_memory.add_user_message(system_prompt)
    st.session_state.conversation = ConversationChain(llm=llm, memory=st.session_state.memory)


# ✅ Function to Calculate Astrology Chart

# First install: pip install pykundli


# def create_vedic_kundli(astro_data):


def calculate_chart(dob, time_of_birth, place_of_birth):
    # Convert to Julian Date
    ist_datetime = datetime.combine(dob, time_of_birth)
    utc_datetime = ist_datetime - timedelta(hours=5, minutes=30)

    # Convert to Julian Day (UTC)
    jd_utc = swe.utc_to_jd(
        utc_datetime.year, utc_datetime.month, utc_datetime.day,
        utc_datetime.hour, utc_datetime.minute, utc_datetime.second,
        swe.GREG_CAL
    )
    jd = jd_utc[1]

    # Geocode birthplace using OpenCage
    oc_api_key = os.getenv("OPENCAGE_API_KEY")
    url = f"https://api.opencagedata.com/geocode/v1/json?q={place_of_birth}&key={oc_api_key}"

    try:
        response = requests.get(url)
        data = response.json()

        if data['results'] and len(data['results']) > 0:
            lat = data['results'][0]['geometry']['lat']
            lon = data['results'][0]['geometry']['lng']
            st.session_state.location_data = {"lat": lat, "lon": lon, "place": place_of_birth}
            print(lat, lon)
        else:
            st.error(f"Could not find coordinates for {place_of_birth}")
            return None
    except Exception as e:
        st.error(f"Error getting location data: {e}")
        return None

    # Planets & Zodiac Signs
    planets = {
        "Sun": swe.SUN, "Moon": swe.MOON, "Mercury": swe.MERCURY, "Venus": swe.VENUS, "Mars": swe.MARS,
        "Jupiter": swe.JUPITER, "Saturn": swe.SATURN, "Rahu": swe.MEAN_NODE,
        "Uranus": swe.URANUS, "Neptune": swe.NEPTUNE, "Pluto": swe.PLUTO
    }
    zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
                    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    nakshatras = ["Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashira", "Ardra", "Punarvasu",
                  "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni", "Hasta", "Chitra",
                  "Swati", "Vishakha", "Anuradha", "Jyeshtha", "Mula", "Purva Ashadha", "Uttara Ashadha",
                  "Shravana", "Dhanishta", "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"]

    # Set sidereal mode for Vedic calculations
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    # Calculate Planetary Positions
    astro_data = {}
    rahu_pos = None  # Store Rahu's position to calculate Ketu's position
    for planet, planet_id in planets.items():
        pos, speed = swe.calc_ut(jd, planet_id, flags=swe.FLG_SIDEREAL)
        degree = round(pos[0], 2)
        sign = zodiac_signs[int(degree // 30)]
        retrograde = speed < 0

        if planet == "Rahu":
            rahu_pos = degree  # Store Rahu's position
            astro_data[planet] = {"Degree": degree, "Sign": sign, "Retrograde": retrograde}
        elif planet == "Ketu":
            # Calculate Ketu's position as 180° opposite Rahu
            if rahu_pos is not None:
                ketu_degree = (rahu_pos + 180) % 360
                ketu_sign = zodiac_signs[int(ketu_degree // 30)]
                astro_data[planet] = {"Degree": ketu_degree, "Sign": ketu_sign, "Retrograde": retrograde}
        else:
            astro_data[planet] = {"Degree": degree, "Sign": sign, "Retrograde": retrograde}

    # Calculate Ascendant (Lagna)
    cusps, ascmc = swe.houses(jd, lat, lon, b'A')  # 'A' = Alcabitius system
    ascendant_degree = round(ascmc[0], 2)
    ascendant_sign = zodiac_signs[int(ascendant_degree // 30)]
    astro_data["Ascendant"] = {"Degree": ascendant_degree, "Sign": ascendant_sign}

    # Calculate Moon Nakshatra (sidereal)
    moon_pos, _ = swe.calc_ut(jd, swe.MOON, flags=swe.FLG_SIDEREAL)
    moon_longitude = moon_pos[0]
    nakshatra_index = int((moon_longitude / (360 / 27))) % 27
    astro_data["Moon Nakshatra"] = nakshatras[nakshatra_index]

    for planet, data in astro_data.items():
        if planet != "Ascendant" and planet != "Moon Nakshatra":
            planet_degree = data["Degree"]
            house_position = 1

            # Find which house the planet is in by comparing its position with house cusps
            for i in range(1, 13):
                next_cusp = cusps[i % 12] if i < 12 else cusps[0]
                current_cusp = cusps[i - 1]

                # Handle the case when a house spans 0 degrees (crosses from Pisces to Aries)
                if next_cusp < current_cusp:
                    if planet_degree >= current_cusp or planet_degree < next_cusp:
                        house_position = i
                        break
                else:
                    if current_cusp <= planet_degree < next_cusp:
                        house_position = i
                        break

            astro_data[planet]["House"] = house_position

    print("\nPlanet House Positions:")
    print("-----------------------")
    for planet, data in astro_data.items():
        if planet != "Ascendant" and planet != "Moon Nakshatra":
            house = data.get("House", "N/A")
            sign = data.get("Sign", "N/A")
            retrograde = "R" if data.get("Retrograde", False) else ""
            print(f"{planet:8} - House {house:2} - {sign:12} {retrograde}")
    return astro_data
     #✅ Step 1: Show Form if No User Details
if st.session_state.user_details is None:
    st.title("Welcome to AstroGPT")
    st.write("Please provide your birth details before starting the chat.")

    with st.form("user_details_form"):
        name = st.text_input("Full Name", placeholder="Enter your name")
        dob = st.date_input("Date of Birth", min_value="1900-01-01", max_value="2025-04-01")
        time_of_birth = st.time_input("Time of Birth")
        place_of_birth = st.text_input("Place of Birth", placeholder="Enter your city")
        submitted = st.form_submit_button("Start Chat")

    if submitted and name and dob and time_of_birth and place_of_birth:
        astro_data = calculate_chart(dob, time_of_birth, place_of_birth)  # Compute Astrology Data
        st.session_state.astro_data = astro_data
        st.session_state.user_details = {
            "name": name,
            "dob": str(dob),
            "time_of_birth": str(time_of_birth),
            "place_of_birth": place_of_birth
        }

        st.session_state.first_message_sent = False
        st.rerun()  # Refresh UI

# ✅ Step 2: Show Chat Interface
if st.session_state.user_details:
    st.title(f"Welcome {st.session_state.user_details['name']} to AstroGPT")
    st.write(
        f"**Birth Details:** {st.session_state.user_details['dob']} | {st.session_state.user_details['time_of_birth']} | {st.session_state.user_details['place_of_birth']}")

    # tab1, tab2 = st.tabs(["Chart", "Data"])
    #
    # with tab1:
     # Visual chart
    #
    # with tab2:
    # show_kundli_table(st.session_state.astro_data)  # Table view
    # ✅ Step 3: AI Response to Kundali (Only Once)
    if not st.session_state.first_message_sent:
        user_query = "Tell me about my kundali based on Chart Json" + str(st.session_state.astro_data)
        response_text = ""

        response_container = st.chat_message("assistant")
        response_placeholder = response_container.empty()

        # ✅ Generate AI response
        for chunk in st.session_state.conversation.run(user_query):
            response_text += chunk
            response_placeholder.write(response_text)
            time.sleep(0.005)

        # ✅ Store response and update flag
        st.session_state.messages.append({"role": "assistant", "content": response_text})
        st.session_state.first_message_sent = True  # ✅ Prevents duplicate first response
        st.rerun()  # Force UI refresh to sync message history

    # ✅ Step 4: Display Chat History (Only Once)
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # ✅ Step 5: User Input for Chat
    user_input = st.chat_input("Ask something about your kundali...")
    if user_input:
        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.write(user_input)

        response_placeholder = st.chat_message("assistant").empty()
        response_text = ""

        # ✅ Generate AI response
        for chunk in st.session_state.conversation.run(user_input):
            response_text += chunk
            response_placeholder.write(response_text)
            time.sleep(0.005)

        st.session_state.messages.append({"role": "assistant", "content": response_text})  # Store response