from flask import Flask, render_template, request, jsonify, send_from_directory
import sqlite3
import os
import requests
GEOAPIFY_API_KEY = "7a17aa6f86fa48f4933664b89e1fea37"
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
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

# ==========================================
# DATABASE CREATION
# ==========================================

def create_database():

    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()


    cur.execute("""
    CREATE TABLE IF NOT EXISTS road_data(

        id INTEGER PRIMARY KEY AUTOINCREMENT,


        latitude REAL,

        longitude REAL,


        road_name TEXT,

        area TEXT,

        city TEXT,

        state TEXT,

        country TEXT,


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

def get_location_name(latitude, longitude):
    try:
        url = (
            f"https://nominatim.openstreetmap.org/reverse"
            f"?format=jsonv2&lat={latitude}&lon={longitude}"
        )

        headers = {
            "User-Agent": "AI_Road_Assessment_System"
        }

        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:

            data = response.json()

            address = data.get("address", {})

            return {

                "road_name": address.get("road", ""),

                "area": address.get(
                    "suburb",
                    address.get("neighbourhood", "")
                ),

                "city": address.get(
                    "city",
                    address.get(
                        "town",
                        address.get("village", "")
                    )
                ),

                "state": address.get("state", ""),

                "country": address.get("country", "")

            }

    except Exception as e:

        print("Reverse Geocoding Error:", e)

    return {

        "road_name": "Unknown",

        "area": "",

        "city": "",

        "state": "",

        "country": ""

    }

# ==========================================
# REVERSE GEOCODING
# ==========================================

geolocator = Nominatim(
    user_agent="ai_road_assessment_abhiram",
    timeout=30
)

def get_location_details(latitude, longitude):

    default = {

        "road_name": "Unknown Road",
        "area": "Unknown Area",
        "city": "Unknown City",
        "state": "Unknown State",
        "country": "Unknown Country"

    }


    try:

        url = (
            "https://api.geoapify.com/v1/geocode/reverse?"
            f"lat={latitude}"
            f"&lon={longitude}"
            f"&apiKey={GEOAPIFY_API_KEY}"
        )


        response = requests.get(
            url,
            timeout=10
        )


        data = response.json()


        if "features" not in data or len(data["features"]) == 0:

            print("No location found")

            return default



        address = data["features"][0]["properties"]


        result = {

            "road_name":
                address.get(
                    "street",
                    "Unknown Road"
                ),


            "area":
                address.get(
                    "suburb",
                    address.get(
                        "district",
                        "Unknown Area"
                    )
                ),


            "city":
                address.get(
                    "city",
                    address.get(
                        "town",
                        "Unknown City"
                    )
                ),


            "state":
                address.get(
                    "state",
                    "Unknown State"
                ),


            "country":
                address.get(
                    "country",
                    "Unknown Country"
                )

        }


        print("LOCATION FOUND:")
        print(result)


        return result



    except Exception as e:

        print("LOCATION ERROR:", e)

        return default
# ==========================================
# HOME DASHBOARD
# ==========================================

@app.route("/")
def home():

    conn = sqlite3.connect(DATABASE)

    conn.row_factory = sqlite3.Row

    cur = conn.cursor()


    # ==========================================
    # Latest record
    # ==========================================

    cur.execute("""
    SELECT *

    FROM road_data

    ORDER BY id DESC

    LIMIT 1
    """)

    latest = cur.fetchone()



    # ==========================================
    # Total scans
    # ==========================================

    cur.execute("""
    SELECT COUNT(*)

    FROM road_data
    """)

    total = cur.fetchone()[0]



    # ==========================================
    # Healthy roads count
    # ==========================================

    cur.execute("""
    SELECT COUNT(*)

    FROM road_data

    WHERE ai_prediction LIKE '%Healthy%'

    OR road_health LIKE '%Excellent%'
    """)

    healthy_count = cur.fetchone()[0]



    # ==========================================
    # Damaged roads count
    # ==========================================

    cur.execute("""
    SELECT COUNT(*)

    FROM road_data

    WHERE ai_prediction LIKE '%Damaged%'
    """)

    damaged_count = cur.fetchone()[0]



    # ==========================================
    # Average AI confidence
    # ==========================================

    cur.execute("""
    SELECT AVG(confidence)

    FROM road_data

    WHERE confidence > 0
    """)

    avg_confidence = cur.fetchone()[0]


    if avg_confidence is None:

        avg_confidence = 0



    # ==========================================
    # Recent road records
    # ==========================================

    cur.execute("""
    SELECT

    road_name,

    area,

    city,

    ai_prediction,

    severity,

    timestamp


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


@app.route("/latest_location")
def latest_location():

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()

    cur.execute("""

    SELECT

    latitude,
    longitude,

    road_name,
    area,
    city,

    health_score,
    road_health,

    vibration,
    speed,

    timestamp

    FROM road_data

    ORDER BY id DESC

    LIMIT 1

    """)

    row = cur.fetchone()

    conn.close()

    if row:

        return jsonify({

            "latitude": row["latitude"],
            "longitude": row["longitude"],

            "road_name": row["road_name"],
            "area": row["area"],
            "city": row["city"],

            "health_score": row["health_score"],
            "road_health": row["road_health"],

            "vibration": row["vibration"],
            "speed": row["speed"],

            "timestamp": row["timestamp"]

        })

    return jsonify({})

@app.route("/map_history")
def map_history():

    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row

    cur = conn.cursor()

    cur.execute("""

    SELECT

    MIN(id) as id,

    latitude,
    longitude,

    road_name,
    area,
    city,

    health_score,
    road_health,

    vibration,
    speed,

    timestamp

    FROM road_data

    GROUP BY

    ROUND(latitude,5),

    ROUND(longitude,5)

    ORDER BY id DESC

    """)

    rows = cur.fetchall()

    conn.close()

    return jsonify([dict(row) for row in rows])

@app.route("/test_location")
def test_location():

    result = get_location_details(
        9.9676839,
        76.3298908
    )

    return jsonify(result)



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



    # ==========================================
    # AI MODEL PREDICTION
    # ==========================================

    result = analyze_road(filepath)


    prediction = result["prediction"]
    confidence = result["confidence"]
    health = result["health"]
    severity = result["severity"]
    recommendation = result["recommendation"]




    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()



    # ==========================================
    # GET LAST MOBILE SENSOR LOCATION
    # ==========================================

    cur.execute("""
    SELECT

    latitude,
    longitude,

    road_name,
    area,
    city,
    state,
    country,

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


        road_name = sensor[2]
        area = sensor[3]
        city = sensor[4]
        state = sensor[5]
        country = sensor[6]


        speed = sensor[7]
        vibration = sensor[8]


        health_score = sensor[9]
        road_health = sensor[10]



    else:


        latitude = 0
        longitude = 0


        road_name = "Unknown"
        area = "Unknown"
        city = "Unknown"
        state = "Unknown"
        country = "Unknown"


        speed = 0
        vibration = 0


        health_score = 0
        road_health = "Unknown"





    # ==========================================
    # SAVE AI RESULT WITH LOCATION
    # ==========================================


    cur.execute("""
    INSERT INTO road_data
    (

    latitude,
    longitude,


    road_name,
    area,
    city,
    state,
    country,


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


    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)


    """,

    (

    latitude,
    longitude,


    road_name,
    area,
    city,
    state,
    country,


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
@app.route("/upload", methods=["POST"])

@app.route("/upload", methods=["POST"])
@app.route("/upload", methods=["POST"])
def upload():

    data = request.get_json()

    print("\n========== RECEIVED SENSOR DATA ==========")
    print(data)


    # ==============================
    # GET SENSOR DATA
    # ==============================

    latitude = data["latitude"]
    longitude = data["longitude"]

    speed = data["speed"]

    # Android already removed gravity
    vibration = data["vibration"]


    print("Latitude:", latitude)
    print("Longitude:", longitude)
    print("Speed:", speed)
    print("Vibration:", vibration)

    # ==============================
# CALCULATE ROAD HEALTH
# ==============================

    if vibration < 2:
        health_score = 95
        road_health = "Excellent 🟢"


    elif vibration < 4:
        health_score = 85
        road_health = "Good 🟢"


    elif vibration < 7:
        health_score = 70
        road_health = "Slight Damage 🟡"


    elif vibration < 10:
        health_score = 50
        road_health = "Moderate Damage 🟠"


    elif vibration < 13:
        health_score = 30
        road_health = "Poor 🔴"


    else:
        health_score = 15
        road_health = "Critical 🔴"

    print("--------------------------------")
    print("Calculated Health Score:", health_score)
    print("Calculated Road Status:", road_health)
    print("--------------------------------")



    # ==============================
    # CHECK GPS
    # ==============================


    if latitude == 0 or longitude == 0:

        return jsonify({

            "status":"error",

            "message":"Invalid GPS location"

        })



    # ==============================
    # GET LOCATION DETAILS
    # ==============================


    location = get_location_details(
        latitude,
        longitude
    )


    road_name = location["road_name"]
    area = location["area"]
    city = location["city"]
    state = location["state"]
    country = location["country"]




    # ==============================
    # DATABASE CONNECTION
    # ==============================


    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()



    # ==============================
    # INSERT ROAD DATA
    # ==============================


    cur.execute("""

    INSERT INTO road_data

    (

    latitude,
    longitude,


    road_name,
    area,
    city,
    state,
    country,


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


    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)


    """,

    (

    latitude,
    longitude,


    road_name,
    area,
    city,
    state,
    country,


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



    # ==============================
    # SAVE DATABASE
    # ==============================


    conn.commit()

    conn.close()



    print("✓ Sensor Data Stored Successfully")



    return jsonify({

        "status":"success",

        "message":"Data Stored Successfully",

        "health_score":health_score,

        "road_health":road_health,

        "vibration": vibration,

    "road_name": road_name,

    "area": area,

    "city": city

    })
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

    road_name,
    area,
    city,

    health_score,
    road_health,

    vibration,
    speed,

    timestamp

    FROM road_data

    ORDER BY id DESC

    LIMIT 50

    """)


    rows = cur.fetchall()


    conn.close()


    data=[]


    for row in rows:

        data.append({

            "latitude": row["latitude"],

            "longitude": row["longitude"],


            "road_name": row["road_name"],

            "area": row["area"],

            "city": row["city"],


            "health_score": row["health_score"],

            "road_health": row["road_health"],


            "vibration": row["vibration"],

            "speed": row["speed"],


            "timestamp": row["timestamp"]

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