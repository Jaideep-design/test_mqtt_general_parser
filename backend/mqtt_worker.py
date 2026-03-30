import threading
import time
from typing import List, Dict, Any, Optional

from paho.mqtt import client as mqtt

from .parser_logic import parse_packet, validate_registers
from .shared_state import update_latest

# Global worker state
_worker_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()

_current_config_lock = threading.Lock()
_current_config: Dict[str, Any] = {
    "broker": None,
    "port": 1883,
    "topic": None,
    "device_id": None,
    "registers": None,
}

def _mqtt_loop():
    """Background loop that connects to MQTT and listens for messages."""
    global _stop_event

    with _current_config_lock:
        broker = _current_config["broker"]
        port = _current_config["port"]
        topic = _current_config["topic"]
        device_id = _current_config["device_id"]
        registers = _current_config["registers"]

    if not broker or not topic or not registers:
        # Misconfigured
        return

    client = mqtt.Client()

    def on_connect(client, userdata, flags, rc):
        # Subscribe to topic
        client.subscribe(topic)

    def on_message(client, userdata, msg):
        raw = msg.payload.decode("utf-8", "ignore")
        parsed_rows = parse_packet(raw, registers)
        update_latest(raw, parsed_rows, device_id, topic)

    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(broker, port, 60)
    except Exception as e:
        print(f"[MQTT] Connection error: {e}")
        return

    # Main loop
    while not _stop_event.is_set():
        client.loop(timeout=1.0)
        time.sleep(0.1)

    client.disconnect()


def configure_and_start_mqtt(
    broker: str,
    port: int,
    topic: str,
    device_id: str,
    registers: List[Dict[str, Any]],
):
    """
    Called by the API when user updates configuration (topic/device/dictionary).
    Stops any existing worker and starts a new one.
    """
    global _worker_thread, _stop_event

    # Validate registers
    validate_registers(registers)

    # Stop existing worker if running
    if _worker_thread and _worker_thread.is_alive():
        _stop_event.set()
        _worker_thread.join(timeout=2)

    # Update config
    with _current_config_lock:
        _current_config["broker"] = broker
        _current_config["port"] = int(port)
        _current_config["topic"] = topic
        _current_config["device_id"] = device_id
        _current_config["registers"] = registers

    # Start new worker
    _stop_event = threading.Event()
    _worker_thread = threading.Thread(target=_mqtt_loop, daemon=True)
    _worker_thread.start()
