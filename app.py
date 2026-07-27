from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import os
from werkzeug.utils import secure_filename

from predict import analyze_road


# ==========================================
# FLASK APP
# ==========================================

app = Flask(__name__)


# ==========================================
# FOLDERS
# ==========================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


DATA_DIR = os.path.join(BASE_DIR, "data")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")


os.makedirs(DATA_DIR, exist_ok=True)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)



DATABASE = os.path.join(DATA_DIR, "database.db")


app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER



print("Database Path:", DATABASE)




# ==========================================
# DATABASE
# ==========================================

def create_database():

    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()


    cur.execute("""
    CREATE TABLE IF NOT EXISTS road_data(

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        latitude REAL,

        longitude REAL,


        speed REAL,

        vibration REAL,


        health_score INTEGER,

        road_health TEXT,


        ai_prediction TEXT,

        confidence REAL,


        severity TEXT,


        recommendation TEXT,


        image_path TEXT,


        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP

    )
    """)


    conn.commit()

    conn.close()



create_database()




# ==========================================
# HOME DASHBOARD
# ==========================================

@app.route("/")
def home():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row


    cur = conn.cursor()



    # Latest record

    cur.execute("""
    SELECT *

    FROM road_data

    ORDER BY id DESC

    LIMIT 1
    """)


    latest = cur.fetchone()




    # Total scans

    cur.execute("""
    SELECT COUNT(*)

    FROM road_data
    """)


    total = cur.fetchone()[0]




    # Healthy roads count

    cur.execute("""
    SELECT COUNT(*)

    FROM road_data

    WHERE ai_prediction LIKE '%Healthy%'

    OR road_health LIKE '%Excellent%'
    """)


    healthy_count = cur.fetchone()[0]




    # Damaged roads count

    cur.execute("""
    SELECT COUNT(*)

    FROM road_data

    WHERE ai_prediction LIKE '%Damaged%'
    """)


    damaged_count = cur.fetchone()[0]




    # Average AI confidence

    cur.execute("""
    SELECT AVG(confidence)

    FROM road_data

    WHERE confidence > 0
    """)


    avg_confidence = cur.fetchone()[0]


    if avg_confidence is None:

        avg_confidence = 0




    # Recent records

    cur.execute("""
    SELECT *

    FROM road_data

    ORDER BY id DESC

    LIMIT 10
    """)


    records = cur.fetchall()



    conn.close()



    return render_template(

        "index.html",

        latest=latest,

        total=total,

        healthy_count=healthy_count,

        damaged_count=damaged_count,

        avg_confidence=round(avg_confidence,2),

        records=records

    )



# ==========================================
# AI IMAGE ANALYSIS
# ==========================================

@app.route("/predict", methods=["POST"])

def predict():

    if "road_image" not in request.files:

        return "No image uploaded"



    file = request.files["road_image"]



    if file.filename == "":

        return "No file selected"



    filename = secure_filename(file.filename)



    filepath = os.path.join(

        app.config["UPLOAD_FOLDER"],

        filename

    )



    file.save(filepath)



    # AI MODEL PREDICTION

    result = analyze_road(filepath)



    prediction = result["prediction"]

    confidence = result["confidence"]

    health = result["health"]

    severity = result["severity"]

    recommendation = result["recommendation"]



    # ==========================================
    # GET LAST SENSOR DATA
    # ==========================================

    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()



    cur.execute("""
SELECT

latitude,

longitude,

speed,

vibration,

health_score,

road_health

FROM road_data

WHERE latitude IS NOT NULL

AND longitude IS NOT NULL

ORDER BY id DESC

LIMIT 1

""")

    sensor = cur.fetchone()




    if sensor:


        latitude = sensor[0]

        longitude = sensor[1]

        speed = sensor[2]

        vibration = sensor[3]

        health_score = sensor[4]

        road_health = sensor[5]


    else:


        latitude = 0

        longitude = 0

        speed = 0

        vibration = 0

        health_score = 0

        road_health = "Unknown"





    # ==========================================
    # SAVE AI RESULT
    # ==========================================


    cur.execute("""
    INSERT INTO road_data
    (

    latitude,

    longitude,


    speed,

    vibration,


    health_score,

    road_health,


    ai_prediction,

    confidence,


    severity,

    recommendation,


    image_path

    )


    VALUES(?,?,?,?,?,?,?,?,?,?,?)

    """,

    (

    latitude,

    longitude,


    speed,

    vibration,


    health_score,

    road_health,


    prediction,

    confidence,


    severity,

    recommendation,


    filename

    ))



    conn.commit()

    conn.close()



    return render_template(

        "result.html",

        image=filename,

        prediction=prediction,

        confidence=confidence,

        health=health,

        severity=severity,

        recommendation=recommendation

    )




# ==========================================
# SHOW UPLOADED IMAGE
# ==========================================


@app.route("/uploads/<filename>")

def uploaded_file(filename):

    return send_from_directory(

        app.config["UPLOAD_FOLDER"],

        filename

    )




# ==========================================
# ANDROID SENSOR API
# ==========================================


@app.route("/upload", methods=["POST"])

def upload():

    data = request.get_json()



    print("\n========== Received Data ==========")

    print(data)



    latitude = data["latitude"]

    longitude = data["longitude"]

    speed = data["speed"]

    vibration = data["vibration"]

    health_score = data["health_score"]

    road_health = data["road_health"]



    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()



    cur.execute("""
    INSERT INTO road_data
    (

    latitude,

    longitude,


    speed,

    vibration,


    health_score,

    road_health,


    ai_prediction,

    confidence,


    severity,

    recommendation,


    image_path

    )


    VALUES(?,?,?,?,?,?,?,?,?,?,?)

    """,

    (

    latitude,

    longitude,


    speed,

    vibration,


    health_score,

    road_health,


    "",

    0,


    "",

    "",


    ""

    ))



    conn.commit()

    conn.close()



    print("✓ Sensor Data Stored")



    return jsonify({

        "status":"success",

        "message":"Data Stored Successfully"

    })




# ==========================================
# VIEW DATABASE
# ==========================================


@app.route("/view")

def view():


    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row


    cur = conn.cursor()



    cur.execute("""

    SELECT *

    FROM road_data

    ORDER BY id DESC

    """)



    rows = cur.fetchall()



    conn.close()



    return jsonify(

        [dict(row) for row in rows]

    )




# ==========================================
# MAP DATA API
# ==========================================


@app.route("/map_data")

def map_data():


    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row


    cur = conn.cursor()



    cur.execute("""

    SELECT

    latitude,

    longitude,

    health_score,

    road_health,

    ai_prediction,

    severity


    FROM road_data


    ORDER BY id DESC

    """)



    rows = cur.fetchall()



    conn.close()



    data = []



    for row in rows:


        data.append({

            "latitude": row["latitude"],

            "longitude": row["longitude"],

            "health_score": row["health_score"],

            "road_health": row["road_health"],

            "prediction": row["ai_prediction"],

            "severity": row["severity"]

        })



    return jsonify(data)




# ==========================================
# MAP PAGE
# ==========================================


@app.route("/map")

def road_map():

    return render_template("map.html")


@app.route("/clear")
def clear():

    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()

    cur.execute("DELETE FROM road_data")

    conn.commit()

    conn.close()

    return "Database cleared"



# ==========================================
# RUN SERVER
# ==========================================


if __name__ == "__main__":


    app.run(

        host="0.0.0.0",

        port=5000,

        debug=True

    )