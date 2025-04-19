import os
import board
import busio
import csv
import datetime
import time
from adafruit_pn532.i2c import PN532_I2C

# Initialize I2C interface
i2c = busio.I2C(board.SCL, board.SDA)

# Create an instance of the PN532 class
pn532 = PN532_I2C(i2c, debug=False)

# Get firmware version
ic, ver, rev, support = pn532.firmware_version
print(f"Found PN532 with firmware version: {ver}.{rev}")

# Configure the reader
pn532.SAM_configuration()

# File paths
CHIP_DATA_FILE = "chip_data.csv"
SCAN_STATUS_FILE = "scan_status.csv"

# Dictionary to store known chip data
known_chips = {}

# Function to load known chips from the CSV file
# Function to load known chips from the CSV file
def load_known_chips():
    global known_chips  # Ensure we modify the global dictionary
    known_chips.clear()  # Clear old data before reloading

    if not os.path.exists(CHIP_DATA_FILE):
        print(f"{CHIP_DATA_FILE} not found. Starting with an empty database.")
        return

    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            uid = row["UID"]
            known_chips[uid] = row  # Reload only current entries


# Function to initialize scan_status.csv with known UIDs
def initialize_scan_status():
    if not os.path.exists(SCAN_STATUS_FILE):
        with open(SCAN_STATUS_FILE, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Sample UID", "Web scan", "Host scan", "new"])  # Write header

    existing_entries = {}
    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            existing_entries[row["Sample UID"]] = row

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Sample UID", "Web scan", "Host scan", "new"])
        for uid in known_chips:
            if uid in existing_entries:
                writer.writerow([uid, existing_entries[uid]["Web scan"], existing_entries[uid]["Host scan"], existing_entries[uid]["new"]])
            else:
                writer.writerow([uid, "False", "False", "False"])

# Function to update scan status
def update_scan_status(uid, is_new):
    load_known_chips()  # Reload the latest chip data
    initialize_scan_status()  # Reload scan status to detect updates

    rows = []
    found = False
    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Sample UID"] == uid:
                row["Host scan"] = "True"
                row["new"] = "True" if is_new else row["new"]
                found = True
            rows.append(row)

    if not found and is_new:
        rows.append({"Sample UID": uid, "Web scan": "False", "Host scan": "True", "new": "True"})

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Sample UID", "Web scan", "Host scan", "new"])
        writer.writeheader()
        writer.writerows(rows)

    if is_new:
        while True:
            load_known_chips()  # Reload chip data to reflect app.py changes
            with open(SCAN_STATUS_FILE, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Sample UID"] == uid and row["Web scan"] == "True":
                        break
                else:
                    time.sleep(1)
                    continue
                break
        for row in rows:
            if row["Sample UID"] == uid:
                row["Host scan"] = "False"
                row["new"] = "False"
                row["Web scan"] = "False"  # Ensure Web scan is reset as well
    else:
        time.sleep(3)
        for row in rows:
            if row["Sample UID"] == uid:
                row["Host scan"] = "False"

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Sample UID", "Web scan", "Host scan", "new"])
        writer.writeheader()
        writer.writerows(rows)

# Load known chips at the start
load_known_chips()
initialize_scan_status()

print("Waiting for an NFC card...")

# Main loop
while True:
    load_known_chips()  # Ensure the latest chip data is used
    initialize_scan_status()  # Ensure scan status is always up to date
    
    uid = pn532.read_passive_target(timeout=0.1)  # Reduced timeout for faster updates
    if uid:
        uid_hex = uid.hex()
        is_new = uid_hex not in known_chips
        if not is_new:
            chip_data = known_chips[uid_hex]
            print(f"""
Recognized Chip:
    Sample ID: {chip_data['ID']}
    UID: {chip_data['UID']}
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