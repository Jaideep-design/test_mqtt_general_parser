import os
import json
import requests
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh
from dictionary_utils import excel_to_json
from collections import deque
if "history" not in st.session_state:
    st.session_state.history = deque(maxlen=2000)

from pathlib import Path

LOG_DIR = Path("mqtt_logs")
LOG_DIR.mkdir(exist_ok=True)


def get_daily_file(device_id):
    date_str = pd.Timestamp.now(tz="Asia/Kolkata").strftime("%Y-%m-%d")
    return LOG_DIR / f"{device_id}_{date_str}.csv"


def append_row_to_csv(row_dict, device_id):
    file_path = get_daily_file(device_id)

    df = pd.DataFrame([row_dict])

    file_exists = file_path.exists()

    df.to_csv(
        file_path,
        mode="a",
        header=not file_exists,
        index=False
    )
# ------------------------------------------------------------------------------
# Streamlit Config
# ------------------------------------------------------------------------------
st.set_page_config(page_title="AC MQTT Live Parser", layout="wide")

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
# st.write("Backend URL =", BACKEND_BASE_URL)

st.title("📡 AC Dictionary → JSON → Live MQTT Parser")


# ------------------------------------------------------------------------------
# session_state initialization
# ------------------------------------------------------------------------------
DEFAULTS = {
    "device_id": "EZMCISAC00097",
    "topic": "/AC/1/EZMCISAC00097/Datalog",
    "broker": "ecozen.ai",
    "port": 1883,
    "registers": None,
    "latest_data": None
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ------------------------------------------------------------------------------
# INPUTS
# ------------------------------------------------------------------------------
st.subheader("Dictionary & MQTT Configuration")

# col_a, col_b = st.columns(2)
col_a, = st.columns(1)
with col_a:
    st.session_state.device_id = st.text_input(
        "Device ID",
        value=st.session_state.device_id
    )

    st.session_state.topic = st.text_input(
        "MQTT Subscriber Topic",
        value=f"/AC/1/{st.session_state.device_id}/Datalog",
    )

# with col_b:
#     st.session_state.broker = st.text_input(
#         "MQTT Broker",
#         value=st.session_state.broker
#     )
#     st.session_state.port = st.number_input(
#         "MQTT Port",
#         value=st.session_state.port,
#         step=1
#     )

uploaded_excel = st.file_uploader("Upload Dictionary Excel", type=["xlsx"])


# ------------------------------------------------------------------------------
# Excel → JSON conversion
# ------------------------------------------------------------------------------
if uploaded_excel and st.button("Convert Excel → JSON"):
    try:
        registers = excel_to_json(uploaded_excel)
        st.session_state.registers = registers

        st.success("✅ Dictionary JSON generated from Excel")
        st.json(registers[:5])

        st.download_button(
            "Download dictionary.json",
            json.dumps(registers, indent=2),
            "dictionary.json",
            "application/json",
        )
    except Exception as e:
        st.error(f"Error during conversion: {e}")

st.markdown("---")


# ------------------------------------------------------------------------------
# Configure Backend
# ------------------------------------------------------------------------------
st.header("Configure Backend MQTT Listener")

if st.button("🚀 Send Configuration to Backend"):
    if not st.session_state.registers:
        st.error("Please convert an Excel dictionary first!")
    else:
        payload = {
            "device_id": st.session_state.device_id,
            "topic": st.session_state.topic,
            "registers": st.session_state.registers,
            "broker": st.session_state.broker,
            "port": int(st.session_state.port),
        }
        try:
            resp = requests.post(
                f"{BACKEND_BASE_URL}/configure",
                json=payload,
                timeout=10
            )
            if resp.status_code == 200:
                st.success(f"Backend configured: {resp.json()}")
            else:
                st.error(f"Backend error {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Could not reach backend: {e}")

st.markdown("---")


# ------------------------------------------------------------------------------
# LIVE DATA VIEWER (Auto-refresh every 5s)
# ------------------------------------------------------------------------------
st.header("Live Data Viewer")

auto_refresh = st.checkbox("🔄 Auto-refresh every 5 seconds")

if auto_refresh:
    st_autorefresh(interval=5000, key="mqtt_autorefresh")

col1, col2 = st.columns([1, 2])

with col1:
    if st.button("Manual Refresh Latest Message"):
        try:
            resp = requests.get(f"{BACKEND_BASE_URL}/latest", timeout=5)
            if resp.status_code == 200:
                st.session_state.latest_data = resp.json()
                latest = st.session_state.latest_data
            else:
                st.error(f"Backend error {resp.status_code}: {resp.text}")
        except Exception as e:
            st.error(f"Could not reach backend: {e}")

# Auto-refresh handling
if auto_refresh:
    try:
        resp = requests.get(f"{BACKEND_BASE_URL}/latest", timeout=5)
        if resp.status_code == 200:
            st.session_state.latest_data = resp.json()
            latest = st.session_state.latest_data
        else:
            st.error(f"Backend error {resp.status_code}: {resp.text}")
    except Exception as e:
        st.error(f"Could not reach backend: {e}")

with col2:
    latest = st.session_state.latest_data
    if latest:
        device_id = latest.get("device_id") or st.session_state.device_id
        raw_message = latest.get("raw")
    
    if latest:
        st.subheader("📦 Latest Raw Packet")
        st.code(latest.get("raw") or "No data yet")

        parsed_rows = latest.get("parsed")

        if parsed_rows:
            df = pd.DataFrame(parsed_rows)

            # Only keep Short name and Value
            df_reduced = df[['Short name', 'Value']].copy()

            # Transpose: shortnames -> columns
            df_transposed = df_reduced.set_index("Short name").T

            # Create IST timestamp
            timestamp_ist = pd.Timestamp.now(tz="Asia/Kolkata")

            parsed_json = json.dumps(parsed_rows, default=str)

            log_row = {
                "timestamp_ist": timestamp_ist.isoformat(),
                "device_id": device_id,
                "raw_message": raw_message,
                "parsed_json": parsed_json
            }

            # Insert timestamp as first column
            df_transposed.insert(0, "timestamp", timestamp_ist)

            st.subheader("🧩 Latest Parsed Message (Cleaned, Transposed, IST Time)")
            st.dataframe(df_transposed)

            # Add to history if new
            # Strong dedup using raw message
            if "last_raw" not in st.session_state:
                st.session_state.last_raw = None
            
            is_new = raw_message and raw_message != st.session_state.last_raw
            
            if is_new:
                st.session_state.last_raw = raw_message
                st.session_state.history.append(df_transposed)
            
                # ✅ Persist to CSV
                append_row_to_csv(log_row, device_id)

        else:
            st.info("No parsed data yet – waiting for MQTT messages.")

    else:
        st.info("Click 'Manual Refresh Latest Message' to fetch current data.")


# # ------------------------------------------------------------------------------
# # SHOW HISTORY
# # ------------------------------------------------------------------------------
# st.markdown("---")
# st.subheader("📜 History of Parsed Messages (latest first, IST timestamps)")

# if st.session_state.history:
#     # Concatenate all rows into a single df
#     history_df = pd.concat(st.session_state.history, ignore_index=True)

#     # Ensure timestamp stays first column
#     cols = ["timestamp"] + [c for c in history_df.columns if c != "timestamp"]
#     history_df = history_df[cols]

#     # Show latest message at TOP
#     history_df = history_df.iloc[::-1].reset_index(drop=True)

#     st.dataframe(history_df)

# else:
#     st.info("No history available yet.")

# ------------------------------------------------------------------------------
# SHOW HISTORY (Decreasing order, capped, IST timestamps)
# ------------------------------------------------------------------------------
st.markdown("---")
st.subheader("📜 History of Parsed Messages")

if st.session_state.history:
    # Convert deque → list → dataframe
    history_df = pd.concat(list(st.session_state.history), ignore_index=True)

    # Ensure timestamp remains FIRST column
    cols = ["timestamp"] + [c for c in history_df.columns if c != "timestamp"]
    history_df = history_df[cols]

    # Sort newest → oldest
    history_df = history_df.iloc[::-1].reset_index(drop=True)

    # Show only last 50 rows in the UI for performance
    # display_df = history_df.head(50)

    # st.caption("Showing latest 50 rows (full history stored up to 2000 rows).")
    st.dataframe(history_df, use_container_width=True)

else:
    st.info("No history available yet.")

st.markdown("---")
st.subheader("📥 Download Logs")

device_id = st.session_state.device_id
daily_file = get_daily_file(device_id)

if daily_file.exists():
    with open(daily_file, "rb") as f:
        st.download_button(
            label="⬇️ Download Today's CSV",
            data=f,
            file_name=daily_file.name,
            mime="text/csv"
        )
else:
    st.info("No logs available yet for today.")
