from flask import Flask, render_template_string, jsonify, request, redirect, url_for, send_from_directory
import os
import csv
import datetime
import time
import threading
from werkzeug.utils import secure_filename

app = Flask(__name__)  # Create the Flask app

# Path to the files
CHIP_DATA_FILE = "chip_data.csv"
SCAN_STATUS_FILE = "scan_status.csv"
UPLOAD_FOLDER = "samples"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Function to check for a new scan
def check_new_scan():
    if os.path.exists(SCAN_STATUS_FILE):
        with open(SCAN_STATUS_FILE, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["new"] == "True":
                    return row["Sample UID"]
    return None

@app.route('/')
def display_chip_data():
    html_content = """
    <html>
    <head>
        <title>NFC Chip Data</title>
        <style>
            .section-card {
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 10px;
                padding: 25px;
                margin-bottom: 40px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            }
            .section-card h2 {
                margin-top: 0;
                font-size: 24px;
                color: #333;
                border-bottom: 2px solid #1a73e8;
                padding-bottom: 10px;
                text-align: left;
            }

            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background-color: #f2f4f8;
                margin: 0;
                padding: 20px;
                text-align: center;
                color: #333;
            }
            .container {
                width: 95%;
                max-width: 1100px;
                margin: auto;
                background: white;
                padding: 30px;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            th, td {
                padding: 12px 10px;
                text-align: left;
                border: 1px solid #dee2e6;
            }
            th {
                background-color: #1a73e8;
                color: white;
                font-weight: 600;
            }
            tr:nth-child(even) {
                background-color: #f9f9f9;
            }

            .highlighted {
                background-color: #bdbdbd !important;
            }
            .scan-button {
                background-color: #28a745;
                color: white;
                padding: 20px 40px;
                font-size: 24px;
                border: none;
                cursor: pointer;
                border-radius: 10px;
                transition: 0.3s;
                display: none;
            }
            .scan-button:hover {
                background-color: #218838;
            }
            .archive-btn {
                padding: 5px 10px;
                font-size: 14px;
                background-color: #dc3545;
                color: white;
                border: none;
                border-radius: 5px;
                cursor: pointer;
            }
            h1 {
                font-size: 32px;
                margin-bottom: 30px;
            }
            h2 {
                font-size: 24px;
                margin: 40px 0 10px 0;
                color: #444;
            }
            td a {
                color: #1a73e8;
                text-decoration: none;
                font-weight: 500;
            }
            td a:hover {
                text-decoration: underline;
            }

        </style>
        <script>
            let dropdownOpen = false;
            function updateStatus(uid, status) {
                fetch(`/update_status/${uid}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                    },
                    body: `status=${encodeURIComponent(status)}`
                });
            }

            function fetchChipData() {
                if (dropdownOpen) return;
                fetch('/api/data')
                    .then(response => response.json())
                    .then(response => {
                        const data = response.data;
                        const activeUID = response.active_uid;
                        const tableBody = document.getElementById('chip-table-body');
                        tableBody.innerHTML = '';
                        
                        data.forEach(chip => {
                            const highlightClass = chip["Host scan"] === "True" ? "highlighted" : "";
                            const row = `
                                <tr class="${highlightClass}">
                                    <td><a href="/samples/${chip.DR}" target="_blank" id="sample-link-${chip.UID}">${chip.ID || ''}</a></td>
                                    <td>${chip.UID || ''}</td>
                                    <td>${chip.FID || ''}</td>
                                    <td>${chip.PID || ''}</td>
                                    <td>${chip.SB || ''}</td>
                                    <td>${chip.TB || ''}</td>
                                    <td>${chip.TR || ''}</td>
                                    <td>${chip.DR || ''}</td>
                                    <td>
                                        <select class="status-dropdown" onchange="updateStatus('${chip.UID}', this.value)">
                                            ${["Received", "In Progress", "On Hold", "Report", "Complete"].map(status =>
                                                `<option value="${status}" ${chip.Status === status ? "selected" : ""}>${status}</option>`
                                            ).join("")}
                                        </select>
                                    </td>
                                    <td><button class="archive-btn" onclick="archiveSample('${chip.UID}')">Archive</button></td>

                                </tr>
                            `;
                            tableBody.innerHTML += row;
                        });

                        document.querySelectorAll('select.status-dropdown').forEach(select => {
                            select.addEventListener('focus', () => { dropdownOpen = true; });
                            select.addEventListener('blur', () => {
                                setTimeout(() => { dropdownOpen = false; }, 200);  // slight delay to allow clicking
                            });
                        });

                        if (activeUID) {
                            const link = document.getElementById(`sample-link-${activeUID}`);
                            if (link && confirm("Familiar tag detected. Open sample?")) {
                                link.click();
                            }
                        }
                    });


                fetch('/api/scan_status')
                    .then(response => response.json())
                    .then(status => {
                        let scanButton = document.getElementById('scan-button');
                        if (status.new_scan) {
                            scanButton.style.display = "block";
                            scanButton.onclick = function() {
                                window.location.href = "/add";
                            };
                        } else {
                            scanButton.style.display = "none";
                        }
                    });

                // Load archived
                fetch('/api/archived')
                    .then(response => response.json())
                    .then(data => {
                        const tableBody = document.getElementById('archived-body');
                        tableBody.innerHTML = '';
                        data.forEach(chip => {
                            const row = `
                                <tr>
                                    <td><a href="/samples/${chip.DR}" target="_blank">${chip.ID || ''}</a></td>
                                    <td>${chip.UID || ''}</td>
                                    <td>${chip.FID || ''}</td>
                                    <td>${chip.PID || ''}</td>
                                    <td>${chip.SB || ''}</td>
                                    <td>${chip.TB || ''}</td>
                                    <td>${chip.TR || ''}</td>
                                    <td>${chip.DR || ''}</td>
                                </tr>
                            `;
                            tableBody.innerHTML += row;
                        });
                    });
            }

            function archiveSample(uid) {
                if (confirm("Are you sure you want to archive this sample?")) {
                    window.location.href = "/archive/" + uid;
                }
            }

            document.addEventListener("DOMContentLoaded", () => {
                fetchChipData();
                setInterval(fetchChipData, 1000);
            });
        </script>
    </head>
    <body>
        <div class="container">
            <h1>Sample Log Book</h1>
            <button id="scan-button" class="scan-button">New Sample Detected</button>
            <div class="section-card">
                <h2>Active Samples</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Sample ID</th>
                            <th>UID</th>
                            <th>Field #</th>
                            <th>Project #</th>
                            <th>Sampled By</th>
                            <th>Tested By</th>
                            <th>Tests Run</th>
                            <th>Date Received</th>
                            <th>Status</th>
                            <th>Archive</th>
                        </tr>
                    </thead>
                    <tbody id="chip-table-body"></tbody>
                </table>
            </div>

            <div class="section-card">
                <h2>Archived Samples</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Sample ID</th>
                            <th>UID</th>
                            <th>Field #</th>
                            <th>Project #</th>
                            <th>Sampled By</th>
                            <th>Tested By</th>
                            <th>Tests Run</th>
                            <th>Date Received</th>
                        </tr>
                    </thead>
                    <tbody id="archived-body"></tbody>
                </table>
            </div>

        </div>
    </body>
    </html>
    """
    return render_template_string(html_content)

@app.route('/update_status/<uid>', methods=['POST'])
def update_status(uid):
    new_status = request.form.get('status')
    updated_rows = []

    with open(CHIP_DATA_FILE, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['UID'] == uid:
                row['Status'] = new_status
            updated_rows.append(row)

    with open(CHIP_DATA_FILE, 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=updated_rows[0].keys())
        writer.writeheader()
        writer.writerows(updated_rows)

    return '', 204


@app.route('/api/data')
def get_chip_data():
    if not os.path.exists(CHIP_DATA_FILE):
        return jsonify([])

    data = []
    scan_status = {}
    active_uid = None

    if os.path.exists(SCAN_STATUS_FILE):
        with open(SCAN_STATUS_FILE, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                scan_status[row["Sample UID"]] = row["Host scan"]
                if row["Host scan"] == "True":
                    active_uid = row["Sample UID"]

    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        for row in reader:
            row["Host scan"] = scan_status.get(row["UID"], "False")
            data.append(row)

    return jsonify({"data": data, "active_uid": active_uid})


@app.route('/api/scan_status')
def get_scan_status():
    new_scan_available = False
    if os.path.exists(SCAN_STATUS_FILE):
        with open(SCAN_STATUS_FILE, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["new"] == "True":
                    new_scan_available = True
                    break

    return jsonify({"new_scan": new_scan_available})

@app.route('/samples/<uid>', methods=['GET', 'POST'])
def sample_files(uid):
    sample_dir = os.path.join(UPLOAD_FOLDER, uid)
    os.makedirs(sample_dir, exist_ok=True)

    # Get sample ID for display
    sample_id = uid
    for file_path in [CHIP_DATA_FILE, "archived.csv"]:
        if os.path.exists(file_path):
            with open(file_path, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["DR"] == uid:
                        sample_id = row["ID"]
                        break

    # Handle file upload
    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file.filename:
                filename = secure_filename(file.filename)
                file.save(os.path.join(sample_dir, filename))
        elif 'note' in request.form:
            note = request.form['note'].strip()
            if note:
                timestamp = datetime.datetime.now().strftime("%B %d, %Y %I:%M %p")
                with open(os.path.join(sample_dir, "notes.txt"), "a") as f:
                    f.write(f"[{timestamp}] {note}\n")

    # Show file list
    file_list = os.listdir(sample_dir)
    file_list = [f for f in file_list if f != "notes.txt"]
    files_html = "".join(f'<li><a href="/samples/{uid}/files/{fname}" target="_blank">{fname}</a></li>' for fname in file_list)

    # Show notes
    notes_html = ""
    notes_path = os.path.join(sample_dir, "notes.txt")
    if os.path.exists(notes_path):
        with open(notes_path, "r") as f:
            notes = f.readlines()
        notes_html = "<ul>" + "".join(f"<li>{line.strip()}</li>" for line in notes) + "</ul>"

    return f"""
    <html>
    <head><title>Files for Sample: {sample_id}</title></head>
    <body>
        <h2>Files for Sample: {sample_id}</h2>
        <form method="POST" enctype="multipart/form-data">
            <input type="file" name="file" required>
            <button type="submit">Upload File</button>
        </form>
        <h3>Uploaded Files:</h3>
        <ul>{files_html}</ul>

        <h3>Add Note:</h3>
        <form method="POST">
            <textarea name="note" rows="4" cols="50" placeholder="Enter your note here..." required></textarea><br>
            <button type="submit">Add Note</button>
        </form>

        <h3>Notes:</h3>
        {notes_html if notes_html else "<p>No notes yet.</p>"}

        <br><a href="/">← Back to Table</a>
    </body>
    </html>
    """



@app.route('/samples/<uid>/files/<filename>')
def serve_sample_file(uid, filename):
    sample_dir = os.path.join(UPLOAD_FOLDER, uid)
    return send_from_directory(sample_dir, filename)

@app.route('/add', methods=['GET', 'POST'])
def add_chip_data():
    new_scan = check_new_scan()
    if not new_scan:
        return "No new scan detected.", 400

    if request.method == 'POST':
        form_data = request.form
        new_entry = {
            "ID": form_data["ID"],
            "UID": new_scan,
            "FID": form_data["FID"],
            "PID": form_data["PID"],
            "SB": form_data["SB"],
            "TB": form_data["TB"],
            "TR": form_data["TR"],
            "DR": datetime.datetime.now().strftime("%B %d, %Y %I:%M %p"),
            "Status": "Received"
        }

        file_exists = os.path.exists(CHIP_DATA_FILE)
        with open(CHIP_DATA_FILE, "a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=new_entry.keys())
            if not file_exists:
                writer.writeheader()
            writer.writerow(new_entry)

        rows = []
        with open(SCAN_STATUS_FILE, "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                if row["Sample UID"] == new_scan:
                    row["new"] = "False"
                    row["Web scan"] = "True"
                rows.append(row)

        with open(SCAN_STATUS_FILE, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=["Sample UID", "Web scan", "Host scan", "new"])
            writer.writeheader()
            writer.writerows(rows)

        def reset_web_scan():
            time.sleep(2)
            updated_rows = []
            with open(SCAN_STATUS_FILE, "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row["Sample UID"] == new_scan:
                        row["Web scan"] = "False"
                    updated_rows.append(row)

            with open(SCAN_STATUS_FILE, "w", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=["Sample UID", "Web scan", "Host scan", "new"])
                writer.writeheader()
                writer.writerows(updated_rows)

        threading.Thread(target=reset_web_scan, daemon=True).start()

        return redirect(url_for('display_chip_data'))

    return f"""
    <html>
    <head>
        <title>Add Sample Data</title>
        <style>
            body {{
                font-family: 'Arial', sans-serif;
                text-align: center;
                background-color: #f8f9fa;
            }}
            .container {{
                width: 50%;
                margin: auto;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0px 4px 6px rgba(0, 0, 0, 0.1);
                margin-top: 50px;
            }}
            input, button {{
                padding: 10px;
                margin: 5px;
                width: 80%;
                font-size: 16px;
            }}
            button {{
                background-color: #28a745;
                color: white;
                border: none;
                cursor: pointer;
                border-radius: 5px;
            }}
            button:hover {{
                background-color: #218838;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>Enter Data for {new_scan}</h2>
            <form method="post">
                <input type="text" name="ID" placeholder="Sample ID" required><br>
                <input type="text" name="FID" placeholder="Field #" required><br>
                <input type="text" name="PID" placeholder="Project #" required><br>
                <input type="text" name="SB" placeholder="Sampled By" required><br>
                <input type="text" name="TB" placeholder="Tested By" required><br>
                <input type="text" name="TR" placeholder="Tests Run" required><br>
                <button type="submit">Load</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.route('/archive/<uid>')
def archive_sample(uid):
    chip_rows = []
    archived_row = None

    # Load chip_data.csv and find the row to archive
    with open(CHIP_DATA_FILE, "r") as file:
        reader = csv.DictReader(file)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["UID"] == uid:
                archived_row = row
            else:
                chip_rows.append(row)

    if archived_row:
        # Remove "Status" key if it exists
        archived_row.pop("Status", None)

        # Append to archived.csv
        archive_fields = [key for key in archived_row.keys()]
        with open("archived.csv", "a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=archive_fields)
            if os.stat("archived.csv").st_size == 0:
                writer.writeheader()
            writer.writerow(archived_row)

        # Rewrite chip_data.csv without the archived row
        with open(CHIP_DATA_FILE, "w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chip_rows)

    return redirect(url_for('display_chip_data'))



@app.route('/api/archived')
def get_archived_data():
    data = []
    if os.path.exists("archived.csv"):
        with open("archived.csv", "r") as file:
            reader = csv.DictReader(file)
            for row in reader:
                data.append(row)
    return jsonify(data)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
