import os
import board
import busio
import csv
import datetime
import time
import threading
from flask import Flask, render_template_string, jsonify, request, redirect, url_for
from adafruit_pn532.i2c import PN532_I2C

# Initialize Flask app
app = Flask(__name__)

# File paths
CHIP_DATA_FILE = "chip_data.csv"
SCAN_STATUS_FILE = "scan_status.csv"

# Initialize I2C for NFC scanner
i2c = busio.I2C(board.SCL, board.SDA)
pn532 = PN532_I2C(i2c, debug=False)

# Get firmware version
ic, ver, rev, support = pn532.firmware_version
print(f"Found PN532 with firmware version: {ver}.{rev}")

# Configure NFC reader
pn532.SAM_configuration()

# Dictionary to store known chip data
known_chips = {}

# Function to load known chips from chip_data.csv
def load_known_chips():
    if not os.path.exists(CHIP_DATA_FILE):
        print(f"{CHIP_DATA_FILE} not found. Starting with an empty database.")
        return

    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            uid = row["IUD"]
            known_chips[uid] = row

# Function to initialize scan_status.csv
def initialize_scan_status():
    if not os.path.exists(SCAN_STATUS_FILE):
        with open(SCAN_STATUS_FILE, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Sample IUD", "Web scan", "Host scan", "new"])  # Header

    existing_entries = {}
    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            existing_entries[row["Sample IUD"]] = row

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Sample IUD", "Web scan", "Host scan", "new"])
        for uid in known_chips:
            if uid in existing_entries:
                writer.writerow([uid, existing_entries[uid]["Web scan"], existing_entries[uid]["Host scan"], existing_entries[uid]["new"]])
            else:
                writer.writerow([uid, "False", "False", "False"])

# Function to check for new scans
def check_new_scan():
    while True:
        with open(SCAN_STATUS_FILE, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["new"] == "True":
                    return row["Sample IUD"]
        time.sleep(1)  # Check every second

# Function to update scan status
def update_scan_status(uid, is_new):
    rows = []
    found = False
    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Sample IUD"] == uid:
                row["Host scan"] = "True"
                row["new"] = "True" if is_new else row["new"]
                found = True
            rows.append(row)

    if not found and is_new:
        rows.append({"Sample IUD": uid, "Web scan": "False", "Host scan": "True", "new": "True"})

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Sample IUD", "Web scan", "Host scan", "new"])
        writer.writeheader()
        writer.writerows(rows)

    if is_new:
        # Wait until Web scan is True
        while True:
            with open(SCAN_STATUS_FILE, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Sample IUD"] == uid and row["Web scan"] == "True":
                        break
                else:
                    time.sleep(1)
                    continue
                break

        # Reset scan status
        for row in rows:
            if row["Sample IUD"] == uid:
                row["Host scan"] = "False"
                row["new"] = "False"
    else:
        time.sleep(3)  # Reset existing tags after 3 seconds
        for row in rows:
            if row["Sample IUD"] == uid:
                row["Host scan"] = "False"

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Sample IUD", "Web scan", "Host scan", "new"])
        writer.writeheader()
        writer.writerows(rows)

# Function to scan NFC tags in a background thread
def scan_nfc():
    print("Starting NFC scanning...")
    while True:
        uid = pn532.read_passive_target(timeout=0.5)
        if uid:
            uid_hex = uid.hex()
            is_new = uid_hex not in known_chips
            if not is_new:
                chip_data = known_chips[uid_hex]
                print(f"""
Recognized Chip:
    Sample ID: {chip_data['ID']}
    UID: {chip_data['IUD']}
    Field #: {chip_data['FID']}
    Project #: {chip_data['PID']}
    Sampled By: {chip_data['SB']}
    Tested By: {chip_data['TB']}
    Tests Run: {chip_data['TR']}
    Date Received: {chip_data['DR']}
                """)
            else:
                print("New chip detected")
                print(f"UID: {uid_hex}")
            update_scan_status(uid_hex, is_new)
        else:
            print("No card detected.")

# Flask routes
@app.route('/')
def display_chip_data():
    return render_template_string("<h1>NFC Scanner & Web Interface Running...</h1>")

@app.route('/api/data')
def get_chip_data():
    if not os.path.exists(CHIP_DATA_FILE):
        return jsonify([])

    data = []
    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            data.append(row)

    return jsonify(data)

@app.route('/add', methods=['GET', 'POST'])
def add_chip_data():
    new_scan = check_new_scan()
    if request.method == 'POST':
        form_data = request.form
        new_entry = {
            "ID": form_data["ID"],
            "IUD": new_scan,
            "FID": form_data["FID"],
            "PID": form_data["PID"],
            "SB": form_data["SB"],
            "TB": form_data["TB"],
            "TR": form_data["TR"],
            "DR": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        file_exists = os.path.exists(CHIP_DATA_FILE)
        with open(CHIP_DATA_FILE, "a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=new_entry.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(new_entry)

        # Set Web scan True for 5 seconds
        rows = []
        with open(SCAN_STATUS_FILE, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["Sample IUD"] == new_scan:
                    row["Web scan"] = "True"
                rows.append(row)

        with open(SCAN_STATUS_FILE, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["Sample IUD", "Web scan", "Host scan", "new"])
            writer.writeheader()
            writer.writerows(rows)

        time.sleep(5)

        for row in rows:
            if row["Sample IUD"] == new_scan:
                row["Web scan"] = "False"

        with open(SCAN_STATUS_FILE, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["Sample IUD", "Web scan", "Host scan", "new"])
            writer.writeheader()
            writer.writerows(rows)

        return redirect(url_for('display_chip_data'))

# Start NFC scanning in a separate thread
nfc_thread = threading.Thread(target=scan_nfc, daemon=True)
nfc_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
