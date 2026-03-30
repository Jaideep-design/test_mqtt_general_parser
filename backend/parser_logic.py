import jsonschema
from jsonschema import validate
from typing import List, Dict, Any

# JSON schema for a single register entry
REGISTER_SCHEMA = {
    "type": "object",
    "properties": {
        "short_name": {"type": "string"},
        "index": {"type": "integer", "minimum": 0},
        "total_upto": {"type": "integer", "minimum": 1},
        "format": {"type": "string", "enum": ["ASCII", "DEC", "HEX", "BIN"]},
        "signed": {"type": "boolean"},
        "scaling": {"type": "number"},
        "offset": {"type": "number"}
    },
    "required": ["short_name", "index", "total_upto", "format", "signed", "scaling", "offset"],
}

def validate_register(reg: Dict[str, Any]):
    """Validate a register dict against the schema."""
    validate(instance=reg, schema=REGISTER_SCHEMA)

def validate_registers(registers: List[Dict[str, Any]]):
    for reg in registers:
        validate_register(reg)

def parse_value(raw_val: str, fmt: str, signed: bool, scaling: float, offset: float, size: int):

    if raw_val is None or raw_val == "":
        return None

    raw_val = raw_val.strip()

    if fmt == "ASCII":
        return raw_val

    if fmt == "BIN":
        try:
            num = int(raw_val, 16)
            return format(num, 'b')
        except:
            return raw_val

    if fmt == "DEC":
        try:
            num = int(raw_val, 16)   # 👈 always hex
        except:
            return raw_val

        # ✅ Apply signed logic
        if signed:
            bits = len(raw_val) * 4   # FIXED
            if num >= 2**(bits - 1):
                num -= 2**bits

        return num * scaling + offset

    if fmt == "HEX":
        return raw_val

    return raw_val

def parse_packet(raw_packet: str, registers):

    rows = []

    print("Packet length:", len(raw_packet))

    raw_packet = raw_packet.rstrip("\n")

    for reg in registers:

        idx = reg["index"]
        end = reg["total_upto"]

        segment = raw_packet[idx:end]
        raw_segment = segment.strip()

        value = parse_value(
            raw_segment,
            reg["format"],
            reg["signed"],
            reg["scaling"],
            reg["offset"],
            reg["size"]   # ✅ REQUIRED
        )

        rows.append({
            "Short name": reg["short_name"],
            "Raw": segment,
            "Value": value
        })

    return rows
