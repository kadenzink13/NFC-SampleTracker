from flask import Flask, render_template, request, redirect, url_for, jsonify
import csv
import datetime
import os
import time

app = Flask(__name__)

# File paths
CHIP_DATA_FILE = "zero_chip_data.csv"
SCAN_STATUS_FILE = "scan_status.csv"

# Store last detected Sample ID with expiration time
last_detected_sample = {"id": None, "timestamp": 0}

# Function to load existing chip data
def load_chip_data():
    if not os.path.exists(CHIP_DATA_FILE):
        return []
    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        return list(reader)

# Function to delete a sample by UID
def delete_sample(UID):
    if not os.path.exists(CHIP_DATA_FILE):
        return

    # Read all data except the one to delete
    rows = []
    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["UID"] != UID:
                rows.append(row)

    # Write the filtered data back to the file
    with open(CHIP_DATA_FILE, "w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=["ID", "UID", "FID", "PID", "SB", "TB", "TR", "DR"])
        writer.writeheader()
        writer.writerows(rows)

# Function to get Sample ID from scan_status if Host scan is True and new is False
def get_active_sample():
    global last_detected_sample

    if not os.path.exists(SCAN_STATUS_FILE):
        return None

    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["Host scan"] == "True" and row["new"] == "False":
                sample_UID = row["Sample UID"]
                
                # Match this UID to its Sample ID in chip_data.csv
                chip_data = load_chip_data()
                for chip in chip_data:
                    if chip["UID"] == sample_UID:
                        last_detected_sample = {
                            "id": chip["ID"],
                            "timestamp": time.time()  # Set timestamp for expiration
                        }
                        return chip["ID"]  # Return Sample ID

    # If the last detected sample is still within 2 minutes, keep displaying it
    if time.time() - last_detected_sample["timestamp"] < 120:
        return last_detected_sample["id"]

    return None  # No active sample found

# Function to check for a new UID in scan_status.csv
def get_new_UID():
    if not os.path.exists(SCAN_STATUS_FILE):
        return None

    with open(SCAN_STATUS_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row["new"] == "True":
                return row["Sample UID"]

    return None  # No new UID found

# API route to delete a sample
@app.route("/delete/<UID>", methods=["POST"])
def delete_route(UID):
    delete_sample(UID)
    return jsonify({"success": True})

# Web route to display form and current data
@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        form = request.form
        new_entry = {
            "ID": form["ID"],
            "UID": form["UID"],
            "FID": form["FID"],
            "PID": form["PID"],
            "SB": form["SB"],
            "TB": form["TB"],
            "TR": form["TR"],
            "DR": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Auto timestamp
        }


        # Append new entry to chip_data.csv
        file_exists = os.path.exists(CHIP_DATA_FILE)
        with open(CHIP_DATA_FILE, "a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=new_entry.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(new_entry)

        # Reset 'new' and 'Host scan' for this UID
        if os.path.exists(SCAN_STATUS_FILE):
            rows = []
            with open(SCAN_STATUS_FILE, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Sample UID"] == new_entry["UID"]:
                        row["Host scan"] = "False"
                        row["new"] = "False"
                    rows.append(row)
            with open(SCAN_STATUS_FILE, "w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["Sample UID", "Web scan", "Host scan", "new"])
                writer.writeheader()
                writer.writerows(rows)
                file.flush()         # Force write to disk
                os.fsync(file.fileno())  # Ensure it's committed from OS buffer to disk


        return redirect(url_for("index"))

    # GET request
    new_UID = get_new_UID()
    active_sample = get_active_sample()
    chip_data = load_chip_data()
    return render_template("index.html", chip_data=chip_data, new_UID=new_UID, active_sample=active_sample)


# API route to check for new UIDs in real-time
@app.route("/api/new_UID", methods=["GET"])
def api_new_UID():
    return jsonify({"new_UID": get_new_UID(), "active_sample": get_active_sample()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
