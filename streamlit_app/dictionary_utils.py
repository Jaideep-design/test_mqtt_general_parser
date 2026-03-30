# -*- coding: utf-8 -*-
"""
Created on Thu Nov 27 15:35:20 2025

@author: Admin
"""

import pandas as pd
import jsonschema
from jsonschema import validate
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# JSON Schema for the full register array
# ---------------------------------------------------------------------------
REGISTER_SCHEMA = {
    "type": "object",
    "properties": {
        "short_name": {"type": "string"},
        "index": {"type": "integer", "minimum": 0},
        "total_upto": {"type": "integer", "minimum": 1},
        "size": {"type": "integer", "minimum": 1},
        "format": {"type": "string", "enum": ["ASCII", "DEC", "HEX", "BIN"]},
        "signed": {"type": "boolean"},
        "scaling": {"type": "number"},
        "offset": {"type": "number"},
    },
    "required": [
        "short_name",
        "index",
        "total_upto",
        "size",
        "format",
        "signed",
        "scaling",
        "offset",
    ],
}

LIST_SCHEMA = {
    "type": "array",
    "items": REGISTER_SCHEMA,
}


# ---------------------------------------------------------------------------
# Detect header row in raw Excel files
# ---------------------------------------------------------------------------
def normalize_excel_headers(uploaded_file) -> pd.DataFrame:
    """
    Detect the header row (first row with >=3 non-null cells)
    and return a cleaned DataFrame with those headers applied.
    """

    df_raw = pd.read_excel(uploaded_file, header=None)
    header_row = None

    for i in range(len(df_raw)):
        if df_raw.iloc[i].count() >= 3:  # heuristically detect a header row
            header_row = i
            break

    if header_row is None:
        raise ValueError("Header row not detected — Excel dictionary is malformed.")

    # Extract header and apply
    header = df_raw.iloc[header_row].tolist()
    df = df_raw.iloc[header_row + 1:].copy()
    df.columns = header
    df.dropna(how="all", inplace=True)

    return df


# ---------------------------------------------------------------------------
# Validate a single register entry
# ---------------------------------------------------------------------------
def validate_register(reg: Dict[str, Any]):
    validate(instance=reg, schema=REGISTER_SCHEMA)


# ---------------------------------------------------------------------------
# Validate the entire register list
# ---------------------------------------------------------------------------
def validate_register_list(registers: List[Dict[str, Any]]):
    validate(instance=registers, schema=LIST_SCHEMA)


# ---------------------------------------------------------------------------
# Convert Excel dictionary → JSON register list
# ---------------------------------------------------------------------------
def excel_to_json(uploaded_file) -> List[Dict[str, Any]]:
    """
    Convert an Excel dictionary sheet into a list of validated register dicts.
    Normalizes formats, handles missing values, and enforces schema.
    """

    df = normalize_excel_headers(uploaded_file)

    required_cols = ["Short name", "Index", "Total upto", "Size [byte]", "Data format"]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column in dictionary: {col}")

    registers = []

    for _, row in df.iterrows():

        # Skip empty or invalid rows
        if pd.isna(row["Short name"]) or pd.isna(row["Index"]) or pd.isna(row["Total upto"]):
            continue

        # Normalize format
        fmt = str(row["Data format"]).strip().upper()
        if fmt == "BINARY":
            fmt = "BIN"

        # Scaling factor defaults
        scaling = row.get("Scaling factor")
        if pd.isna(scaling):
            scaling = 1.0

        offset = row.get("Offset")
        if pd.isna(offset):
            offset = 0.0

        # Convert Signed/Unsigned → boolean
        signed_raw = str(row.get("Signed/Unsigned", "U")).strip().upper()
        signed_flag = (signed_raw == "S")

        # Build register dict
        reg = {
            "short_name": str(row["Short name"]).strip().upper(),
            "index": int(row["Index"]),
            "total_upto": int(row["Total upto"]),
            "size" : int(row["Size [byte]"]),
            "format": fmt,
            "signed": signed_flag,
            "scaling": float(scaling),
            "offset": float(offset),
        }
        if reg["total_upto"] <= reg["index"]:
            raise ValueError(
                f"Invalid range for {reg['short_name']} (index >= total_upto)"
            )

        # Validate individual register
        try:
            validate_register(reg)
        except Exception as e:
            raise ValueError(f"Register validation failed for {reg['short_name']}: {e}")

        registers.append(reg)

    # Validate entire list
    try:
        validate_register_list(registers)
    except Exception as e:
        raise ValueError(f"Dictionary validation failed: {e}")

    return registers
