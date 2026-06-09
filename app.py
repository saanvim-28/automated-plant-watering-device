from flask import Flask, jsonify, request
import serial
import threading
import time
import os

app = Flask(__name__)

# --- Config ---
PORT = 'COM4' # The USB port where your Arduino is connected
BAUD = 9600 # Communication speed must match Arduino Serial.begin
WATER_COOLDOWN_SECS = 3 * 60 * 60  # Safety delay: wait 3 hours between watering sessions

# --- State ---
latest_value = None # Stores the most recent moisture reading
last_watered = None # Stores the timestamp of the last watering event
ser = None          # Placeholder for the Serial connection object

# 🌱 default spider plant range (lower is wetter, higher is drier)
min_moisture = 400
max_moisture = 600


def connect_serial():
    """Background thread to handle constant communication with Arduino."""
    global ser, latest_value, last_watered

    while True:
        try:
            # Attempt to establish connection
            ser = serial.Serial(PORT, BAUD, timeout=2)
            print(f"Connected to {PORT}")
            time.sleep(2) # Wait for Arduino to reset after connection

            while True:
                # Read incoming line from Arduino
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue

                print(f"Raw: {line}")

                # If Arduino confirms pump finished: update the timestamp
                if line == "WATERED":
                    last_watered = time.time()
                    print("Pump completed")

                # If Arduino sends a number: update sensor state
                elif line.isdigit():
                    latest_value = int(line)
                    print(f"Sensor: {latest_value}")

                    # Check if enough time has passed since last watering
                    cooldown_ok = (
                        last_watered is None or
                        (time.time() - last_watered) >= WATER_COOLDOWN_SECS
                    )

                    # 💡 FLASK DECISION LOGIC: Trigger pump if too dry and cooldown passed
                    if latest_value > max_moisture and cooldown_ok:
                        ser.write(b"W\n") # Send 'W' command to Arduino
                        print(f"AUTO WATER → {latest_value} > {max_moisture}")

        except Exception as e:
            print(f"Serial error: {e}")
            ser = None # Reset serial object on error
            time.sleep(3) # Wait before attempting to reconnect


# Start the serial monitoring in a separate thread so it doesn't block the website
threading.Thread(target=connect_serial, daemon=True).start()


def format_time_ago(ts):
    """Converts a Unix timestamp into a human-readable 'time ago' string."""
    if ts is None:
        return "Never"
    diff = int(time.time() - ts)
    if diff < 60:
        return f"{diff}s ago"
    elif diff < 3600:
        return f"{diff // 60}m ago"
    return f"{diff // 3600}h ago"


@app.route("/data")
def data():
    """API endpoint for the frontend to get the current plant status."""
    connected = ser is not None and ser.is_open and latest_value is not None

    return jsonify({
        "sensor": latest_value,
        "connected": connected,
        "last_watered": format_time_ago(last_watered),
        "min": min_moisture,
        "max": max_moisture
    })


@app.route("/set_range", methods=["POST"])
def set_range():
    """API endpoint to update moisture thresholds from the web UI."""
    global min_moisture, max_moisture

    data = request.json
    min_moisture = int(data.get("min", min_moisture))
    max_moisture = int(data.get("max", max_moisture))

    return jsonify({"success": True})


@app.route("/water", methods=["POST"])
def water():
    """API endpoint to trigger a manual watering command."""
    if ser is None or not ser.is_open:
        return jsonify({"success": False, "error": "Arduino not connected"}), 503

    try:
        ser.write(b"W\n") # Send the water command to Arduino
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/")
def home():
    """Serves the index.html file to the user's browser."""
    dir = os.path.dirname(os.path.abspath(__file__))
    return open(os.path.join(dir, "index.html"), encoding="utf-8").read()


if __name__ == "__main__":
    app.run(debug=False)