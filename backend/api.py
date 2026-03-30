from typing import Any, Dict, List

import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .shared_state import get_latest_data
from .mqtt_worker import configure_and_start_mqtt


print("🔎 Listing project root:")
print(os.listdir("/opt/render/project/src"))

print("🔎 Listing backend folder:")
print(os.listdir("/opt/render/project/src/backend"))


# Optional: defaults from env vars
DEFAULT_BROKER = os.getenv("MQTT_BROKER", "ecozen.ai")
DEFAULT_PORT = int(os.getenv("MQTT_PORT", "1883"))

app = FastAPI(title="MQTT AC Parser Backend")

class ConfigurePayload(BaseModel):
    device_id: str
    topic: str
    registers: List[Dict[str, Any]]
    broker: str | None = None
    port: int | None = None

@app.get("/")
def root():
    return {"status": "backend ok"}

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/configure")
def configure(payload: ConfigurePayload):
    broker = payload.broker or DEFAULT_BROKER
    port = payload.port or DEFAULT_PORT

    if not payload.device_id:
        raise HTTPException(status_code=400, detail="device_id is required")
    if not payload.topic:
        raise HTTPException(status_code=400, detail="topic is required")
    if not payload.registers:
        raise HTTPException(status_code=400, detail="registers (dictionary) are required")

    # Start or reconfigure MQTT worker
    configure_and_start_mqtt(
        broker=broker,
        port=port,
        topic=payload.topic,
        device_id=payload.device_id,
        registers=payload.registers,
    )

    return {
        "status": "configured",
        "broker": broker,
        "port": port,
        "topic": payload.topic,
        "device_id": payload.device_id,
        "register_count": len(payload.registers),
    }


@app.get("/latest")
def latest():
    data = get_latest_data()
    return data
