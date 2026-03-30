import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import pandas as pd
import streamlit as st
from dictionary_utils import excel_to_json
from backend.parser_logic import parse_packet

st.set_page_config(page_title="Manual Raw Hex Parser", layout="wide")

st.title("📝 Manual Raw Hex Parser (Dictionary → Parse Raw Packet)")

st.write("Upload a dictionary Excel and paste a raw hex string to parse it locally.")


# ------------------------------------------------------------------------------
# Upload dictionary
# ------------------------------------------------------------------------------
st.header("1️⃣ Upload Dictionary Excel")

uploaded_excel = st.file_uploader("Upload Dictionary Excel", type=["xlsx"])

registers = None

if uploaded_excel and st.button("Convert Excel → JSON"):
    try:
        registers = excel_to_json(uploaded_excel)
        st.session_state.manual_registers = registers

        st.success("Dictionary loaded successfully!")
        st.json(registers[:5])

    except Exception as e:
        st.error(f"Error converting dictionary: {e}")


# ------------------------------------------------------------------------------
# Paste RAW hex string
# ------------------------------------------------------------------------------
st.header("2️⃣ Paste Raw Hex String")

raw_hex = st.text_area(
    "Raw Hex Packet",
    placeholder="Paste hex string here (e.g. A10F4B0034FE...)",
    height=150
)


# ------------------------------------------------------------------------------
# Parse Button
# ------------------------------------------------------------------------------
st.header("3️⃣ Parse Packet")

if st.button("Parse Raw Packet"):

    if not raw_hex or raw_hex.strip() == "":
        st.error("Please paste a raw hex string!")
    elif "manual_registers" not in st.session_state:
        st.error("Please upload and convert a dictionary first!")
    else:
        registers = st.session_state.manual_registers

        try:
            parsed = parse_packet(raw_hex.strip(), registers)

            if not parsed:
                st.warning("Parsed output is empty.")
            else:
                df = pd.DataFrame(parsed)
                st.subheader("Parsed DataFrame")
                st.dataframe(df, use_container_width=True)

        except Exception as e:
            st.error(f"Error parsing raw packet: {e}")
