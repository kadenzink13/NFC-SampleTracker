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
def load_known_chips():
    if not os.path.exists(CHIP_DATA_FILE):
        print(f"{CHIP_DATA_FILE} not found. Starting with an empty database.")
        return

    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            uid = row["IUD"]
            known_chips[uid] = row

# Function to initialize scan_status.csv with known IUDs
def initialize_scan_status():
    if not os.path.exists(SCAN_STATUS_FILE):
        with open(SCAN_STATUS_FILE, "w", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Sample IUD", "Web scan", "Host scan"])  # Write header

    existing_entries = {}
    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            existing_entries[row["Sample IUD"]] = row

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Sample IUD", "Web scan", "Host scan"])  # Write header again
        for uid in known_chips:
            if uid in existing_entries:
                writer.writerow([uid, existing_entries[uid]["Web scan"], existing_entries[uid]["Host scan"]])
            else:
                writer.writerow([uid, "False", "False"])

# Function to update scan status
def update_scan_status(uid):
    rows = []
    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Sample IUD"] == uid:
                row["Host scan"] = "True"
            rows.append(row)

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Sample IUD", "Web scan", "Host scan"])
        writer.writeheader()
        writer.writerows(rows)

    time.sleep(2)  # Keep status as True for 2 seconds

    for row in rows:
        if row["Sample IUD"] == uid:
            row["Host scan"] = "False"

    with open(SCAN_STATUS_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["Sample IUD", "Web scan", "Host scan"])
        writer.writeheader()
        writer.writerows(rows)

# Load known chips at the start
load_known_chips()
initialize_scan_status()

print("Waiting for an NFC card...")

# Main loop
while True:
    uid = pn532.read_passive_target(timeout=0.5)
    if uid:
        uid_hex = uid.hex()
        if uid_hex in known_chips:
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
            update_scan_status(uid_hex)
        else:
            print("New chip detected")
            print(f"UID: {uid_hex}")

            # Get chip details from the user
            identifier = input("Enter sample ID: ")
            field_no = input("Enter field #: ")
            project_no = input("Enter project #: ")
            sampled_by = input("Enter sampled by: ")
            tested_by = input("Enter tested by: ")
            tests_run = input("Enter tests run: ")
            date_received = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Save new chip data
            log_chip_data(uid_hex, identifier, field_no, project_no, sampled_by, tested_by, tests_run, date_received)
            initialize_scan_status()
            print(f"Chip {identifier} saved.")
    else:
        print("No card detected.")
