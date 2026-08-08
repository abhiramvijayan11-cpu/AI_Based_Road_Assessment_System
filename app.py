
import json
import os
import sqlite3
from datetime import datetime

import requests

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
)

from werkzeug.utils import secure_filename

from predict import analyze_road

from osm import (
    get_nearest_road,
    get_road_geometry,
    parse_road_geometry,
    create_road_segments,
    save_road_segments,
    find_nearest_segment,
)


# ============================================================
# FLASK APP
# ============================================================

app = Flask(__name__)


# ============================================================
# BASE DIRECTORIES
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.path.join(
    BASE_DIR,
    "data"
)

UPLOAD_FOLDER = os.path.join(
    BASE_DIR,
    "uploads"
)

os.makedirs(
    DATA_DIR,
    exist_ok=True
)

os.makedirs(
    UPLOAD_FOLDER,
    exist_ok=True
)


DATABASE = os.path.join(
    DATA_DIR,
    "database.db"
)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

print("Database Path:", DATABASE)


# ============================================================
# GEOAPIFY
# ============================================================

# IMPORTANT:
# Keep your existing Geoapify key here.
#
# For a real deployment, move this to an environment variable.
#
GEOAPIFY_API_KEY = os.environ.get(
    "GEOAPIFY_API_KEY",
    "7a17aa6f86fa48f4933664b89e1fea37"
)


# ============================================================
# DATABASE CREATION
# ============================================================

def create_database():

    conn = sqlite3.connect(
        DATABASE
    )

    cur = conn.cursor()

    # --------------------------------------------------------
    # SENSOR / AI DATA
    # --------------------------------------------------------

    cur.execute(
        """
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

            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,

            road_id TEXT,
            road_geometry TEXT,

            geometry_cached INTEGER DEFAULT 0
        )
        """
    )

    # --------------------------------------------------------
    # ROAD SEGMENTS
    # --------------------------------------------------------

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS road_segments(

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            road_id TEXT,

            segment_number INTEGER,

            geometry TEXT,

            average_health REAL DEFAULT 100.0,

            total_scans INTEGER DEFAULT 0,

            status TEXT,

            last_update TEXT,

            road_name TEXT
        )
        """
    )

    conn.commit()

    conn.close()


create_database()


# ============================================================
# DATABASE CONNECTION HELPER
# ============================================================

def get_db():

    conn = sqlite3.connect(
        DATABASE
    )

    conn.row_factory = sqlite3.Row

    return conn


# ============================================================
# ROAD HEALTH CALCULATION
# ============================================================

def calculate_health(vibration):

    vibration = float(
        vibration or 0
    )

    if vibration < 2:

        return 95, "Excellent"

    elif vibration < 4:

        return 85, "Good"

    elif vibration < 7:

        return 70, "Slight Damage"

    elif vibration < 10:

        return 50, "Moderate Damage"

    elif vibration < 13:

        return 30, "Poor"

    else:

        return 15, "Critical"


# ============================================================
# HEALTH STATUS FOR MAP
# ============================================================

def health_status(health):

    health = float(
        health or 0
    )

    if health >= 90:

        return "Excellent 🟢"

    elif health >= 80:

        return "Good 🟢"

    elif health >= 60:

        return "Slight Damage 🟡"

    elif health >= 40:

        return "Moderate Damage 🟠"

    elif health >= 20:

        return "Poor 🔴"

    else:

        return "Critical 🔴"


# ============================================================
# DISTANCE BETWEEN GPS POINTS
# ============================================================

def haversine_distance(
    lat1,
    lon1,
    lat2,
    lon2
):

    from math import (
        radians,
        sin,
        cos,
        sqrt,
        atan2
    )

    earth_radius = 6371000.0

    lat1 = radians(lat1)
    lon1 = radians(lon1)

    lat2 = radians(lat2)
    lon2 = radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        sin(dlat / 2) ** 2
        +
        cos(lat1)
        *
        cos(lat2)
        *
        sin(dlon / 2) ** 2
    )

    c = 2 * atan2(
        sqrt(a),
        sqrt(1 - a)
    )

    return earth_radius * c


# ============================================================
# DISTANCE FROM GPS TO ROAD GEOMETRY
# ============================================================

def distance_to_geometry(
    latitude,
    longitude,
    geometry
):

    if not geometry:

        return float("inf")

    minimum_distance = float("inf")

    for point in geometry:

        try:

            point_lat = float(
                point[0]
            )

            point_lon = float(
                point[1]
            )

            distance = haversine_distance(
                latitude,
                longitude,
                point_lat,
                point_lon
            )

            if distance < minimum_distance:

                minimum_distance = distance

        except (
            ValueError,
            TypeError,
            IndexError
        ):

            continue

    return minimum_distance


# ============================================================
# REVERSE GEOCODING - NOMINATIM FALLBACK
# ============================================================

def nominatim_location(
    latitude,
    longitude
):

    try:

        url = (
            "https://nominatim.openstreetmap.org/reverse"
            f"?format=jsonv2"
            f"&lat={latitude}"
            f"&lon={longitude}"
            "&zoom=18"
            "&addressdetails=1"
        )

        headers = {
            "User-Agent":
                "AI_Road_Assessment_System/1.0"
        }

        response = requests.get(
            url,
            headers=headers,
            timeout=10
        )

        if response.status_code != 200:

            print(
                "Nominatim HTTP:",
                response.status_code
            )

            return None

        data = response.json()

        address = data.get(
            "address",
            {}
        )

        # ----------------------------------------------------
        # ROAD
        # ----------------------------------------------------

        road_name = (
            address.get("road")
            or address.get("pedestrian")
            or address.get("path")
            or address.get("footway")
            or data.get("name")
            or "Unknown Road"
        )

        # ----------------------------------------------------
        # AREA
        #
        # We deliberately include county / state_district
        # as fallbacks because some Kerala locations do not
        # provide suburb/neighbourhood.
        # ----------------------------------------------------

        area = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("quarter")
            or address.get("village")
            or address.get("hamlet")
            or address.get("town")
            or address.get("municipality")
            or address.get("county")
            or address.get("state_district")
            or "Unknown Area"
        )

        # ----------------------------------------------------
        # CITY
        # ----------------------------------------------------

        city = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("village")
            or address.get("county")
            or ""
        )

        state = (
            address.get("state")
            or address.get("state_district")
            or ""
        )

        country = (
            address.get("country")
            or ""
        )

        result = {

            "road_name": road_name,

            "area": area,

            "city": city,

            "state": state,

            "country": country
        }

        print(
            "NOMINATIM LOCATION:",
            result
        )

        return result

    except Exception as e:

        print(
            "Nominatim Error:",
            e
        )

        return None


# ============================================================
# REVERSE GEOCODING - GEOAPIFY
# ============================================================

def geoapify_location(
    latitude,
    longitude
):

    if not GEOAPIFY_API_KEY:

        return None

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

        if response.status_code != 200:

            print(
                "Geoapify HTTP:",
                response.status_code
            )

            return None

        data = response.json()

        features = data.get(
            "features",
            []
        )

        if not features:

            print(
                "Geoapify: No location found"
            )

            return None

        address = features[0].get(
            "properties",
            {}
        )

        # ----------------------------------------------------
        # ROAD
        # ----------------------------------------------------

        road_name = (
            address.get("street")
            or address.get("road")
            or address.get("name")
            or "Unknown Road"
        )

        # ----------------------------------------------------
        # AREA
        # ----------------------------------------------------

        area = (
            address.get("suburb")
            or address.get("neighbourhood")
            or address.get("quarter")
            or address.get("district")
            or address.get("village")
            or address.get("town")
            or address.get("municipality")
            or address.get("county")
            or address.get("state_district")
            or address.get("state")
            or "Unknown Area"
        )

        # ----------------------------------------------------
        # CITY
        # ----------------------------------------------------

        city = (
            address.get("city")
            or address.get("town")
            or address.get("municipality")
            or address.get("village")
            or address.get("county")
            or ""
        )

        state = (
            address.get("state")
            or address.get("state_district")
            or ""
        )

        country = (
            address.get("country")
            or ""
        )

        result = {

            "road_name": road_name,

            "area": area,

            "city": city,

            "state": state,

            "country": country
        }

        print(
            "GEOAPIFY LOCATION:",
            result
        )

        return result

    except Exception as e:

        print(
            "Geoapify Error:",
            e
        )

        return None


# ============================================================
# UNIFIED LOCATION FUNCTION
# ============================================================

def get_location_details(
    latitude,
    longitude
):

    default = {

        "road_name":
            "Unknown Road",

        "area":
            "Unknown Area",

        "city":
            "Unknown City",

        "state":
            "Unknown State",

        "country":
            "Unknown Country"
    }

    # --------------------------------------------------------
    # TRY GEOAPIFY
    # --------------------------------------------------------

    result = geoapify_location(
        latitude,
        longitude
    )

    # --------------------------------------------------------
    # TRY NOMINATIM IF GEOAPIFY DID NOT PROVIDE GOOD DATA
    # --------------------------------------------------------

    if result is None:

        result = nominatim_location(
            latitude,
            longitude
        )

    # --------------------------------------------------------
    # IF BOTH FAILED
    # --------------------------------------------------------

    if result is None:

        print(
            "Reverse geocoding failed completely."
        )

        return default

    # --------------------------------------------------------
    # CLEAN EMPTY VALUES
    # --------------------------------------------------------

    for key in default:

        if (
            key not in result
            or result[key] is None
            or str(result[key]).strip() == ""
        ):

            result[key] = default[key]

    print(
        "LOCATION FOUND:"
    )

    print(
        result
    )

    return result


# ============================================================
# HOME DASHBOARD
# ============================================================

@app.route("/")
def home():

    conn = get_db()

    cur = conn.cursor()

    # --------------------------------------------------------
    # LATEST RECORD
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT *
        FROM road_data
        ORDER BY id DESC
        LIMIT 1
        """
    )

    latest = cur.fetchone()

    # --------------------------------------------------------
    # TOTAL SCANS
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT COUNT(*)
        FROM road_data
        """
    )

    total = cur.fetchone()[0]

    # --------------------------------------------------------
    # HEALTHY RECORDS
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT COUNT(*)
        FROM road_data
        WHERE
            road_health LIKE '%Excellent%'
            OR road_health LIKE '%Good%'
            OR ai_prediction LIKE '%Healthy%'
        """
    )

    healthy_count = cur.fetchone()[0]

    # --------------------------------------------------------
    # DAMAGED RECORDS
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT COUNT(*)
        FROM road_data
        WHERE
            road_health LIKE '%Damage%'
            OR road_health LIKE '%Poor%'
            OR road_health LIKE '%Critical%'
            OR ai_prediction LIKE '%Damaged%'
        """
    )

    damaged_count = cur.fetchone()[0]

    # --------------------------------------------------------
    # AVERAGE AI CONFIDENCE
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT AVG(confidence)
        FROM road_data
        WHERE confidence > 0
        """
    )

    avg_confidence = cur.fetchone()[0]

    if avg_confidence is None:

        avg_confidence = 0

    # --------------------------------------------------------
    # RECENT RECORDS
    # --------------------------------------------------------

    cur.execute(
        """
        SELECT
            road_name,
            area,
            city,
            health_score,
            road_health,
            vibration,
            speed,
            ai_prediction,
            confidence,
            severity,
            recommendation,
            timestamp
        FROM road_data
        ORDER BY id DESC
        LIMIT 10
        """
    )

    records = cur.fetchall()

    conn.close()

    return render_template(
        "index.html",
        latest=latest,
        total=total,
        healthy_count=healthy_count,
        damaged_count=damaged_count,
        avg_confidence=round(
            avg_confidence,
            2
        ),
        records=records
    )


# ============================================================
# LATEST LOCATION
# ============================================================

@app.route(
    "/latest_location"
)
def latest_location():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            latitude,
            longitude,
            road_name,
            area,
            city,
            state,
            country,
            health_score,
            road_health,
            vibration,
            speed,
            timestamp
        FROM road_data
        WHERE
            latitude IS NOT NULL
            AND longitude IS NOT NULL
            AND latitude != 0
            AND longitude != 0
        ORDER BY id DESC
        LIMIT 1
        """
    )

    row = cur.fetchone()

    conn.close()

    if row:

        return jsonify(
            dict(row)
        )

    return jsonify({})


# ============================================================
# MAP HISTORY
# ============================================================

@app.route(
    "/map_history"
)
def map_history():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            latitude,
            longitude,
            road_name,
            area,
            city,
            state,
            country,
            health_score,
            road_health,
            vibration,
            speed,
            timestamp
        FROM road_data
        WHERE
            latitude IS NOT NULL
            AND longitude IS NOT NULL
            AND latitude != 0
            AND longitude != 0
        ORDER BY id ASC
        LIMIT 500
        """
    )

    rows = cur.fetchall()

    conn.close()

    return jsonify(
        [
            dict(row)
            for row in rows
        ]
    )


# ============================================================
# TEST LOCATION
# ============================================================

@app.route(
    "/test_location"
)
def test_location():

    # Example location
    result = get_location_details(
        9.8732431,
        76.5251469
    )

    return jsonify(
        result
    )


# ============================================================
# AI IMAGE ANALYSIS
# ============================================================

@app.route(
    "/predict",
    methods=["POST"]
)
def predict():

    if "road_image" not in request.files:

        return jsonify({
            "status": "error",
            "message": "No image uploaded"
        }), 400

    file = request.files[
        "road_image"
    ]

    if not file.filename:

        return jsonify({
            "status": "error",
            "message": "No file selected"
        }), 400

    filename = secure_filename(
        file.filename
    )

    # Prevent filename collisions
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    filename = (
        f"{timestamp}_{filename}"
    )

    filepath = os.path.join(
        app.config["UPLOAD_FOLDER"],
        filename
    )

    file.save(
        filepath
    )

    # --------------------------------------------------------
    # AI MODEL
    # --------------------------------------------------------

    try:

        result = analyze_road(
            filepath
        )

    except Exception as e:

        print(
            "AI Analysis Error:",
            e
        )

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

    prediction = result.get(
        "prediction",
        "Unknown"
    )

    confidence = result.get(
        "confidence",
        0
    )

    health = result.get(
        "health",
        "Unknown"
    )

    severity = result.get(
        "severity",
        "Unknown"
    )

    recommendation = result.get(
        "recommendation",
        ""
    )

    # --------------------------------------------------------
    # GET LAST MOBILE LOCATION
    # --------------------------------------------------------

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
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
        WHERE
            latitude IS NOT NULL
            AND longitude IS NOT NULL
            AND latitude != 0
            AND longitude != 0
        ORDER BY id DESC
        LIMIT 1
        """
    )

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

    return render_template(
        "result.html",
        image=filename,
        prediction=prediction,
        confidence=confidence,
        health=health,
        severity=severity,
        recommendation=recommendation
    )


# ============================================================
# SENSOR UPLOAD
# ============================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    try:

        data = request.get_json(
            silent=True
        )

        if not data:

            return jsonify({
                "status": "error",
                "message": "Invalid JSON data"
            }), 400

        print(
            "\n========== RECEIVED SENSOR DATA =========="
        )

        print(
            data
        )

        # ----------------------------------------------------
        # SENSOR VALUES
        # ----------------------------------------------------

        latitude = float(
            data.get(
                "latitude",
                0
            )
        )

        longitude = float(
            data.get(
                "longitude",
                0
            )
        )

        speed = float(
            data.get(
                "speed",
                0
            )
        )

        vibration = float(
            data.get(
                "vibration",
                0
            )
        )

        # Use Android health values if supplied.
        # Otherwise calculate them here.

        health_score = data.get(
            "health_score"
        )

        road_health = data.get(
            "road_health"
        )

        if health_score is None or not road_health:

            health_score, road_health = (
                calculate_health(
                    vibration
                )
            )

        else:

            health_score = int(
                health_score
            )

        print(
            "Latitude:",
            latitude
        )

        print(
            "Longitude:",
            longitude
        )

        print(
            "Speed:",
            speed
        )

        print(
            "Vibration:",
            vibration
        )

        print(
            "Health Score:",
            health_score
        )

        print(
            "Road Status:",
            road_health
        )

        # ----------------------------------------------------
        # GPS VALIDATION
        # ----------------------------------------------------

        if (
            latitude == 0
            or longitude == 0
        ):

            print(
                "Invalid GPS received."
            )

            return jsonify({
                "status": "ignored",
                "message": "Waiting for valid GPS"
            })

        # ----------------------------------------------------
        # OSM ROAD MATCHING
        # ----------------------------------------------------

        try:

            osm_data = get_nearest_road(
                latitude,
                longitude
            )

        except Exception as e:

            print(
                "OSM road matching error:",
                e
            )

            osm_data = {
                "road_id": None,
                "road_name": "Unknown Road"
            }

        road_id = osm_data.get(
            "road_id"
        )

        osm_road_name = osm_data.get(
            "road_name",
            "Unknown Road"
        )

        print(
            "\n=============================="
        )

        print(
            "OSM ROAD ID:",
            road_id
        )

        print(
            "OSM ROAD NAME:",
            osm_road_name
        )

        print(
            "=============================="
        )

        # ----------------------------------------------------
        # FIND NEAREST SEGMENT
        # ----------------------------------------------------

        segment_number = None

        if road_id is not None:

            try:

                segment_number = (
                    find_nearest_segment(
                        latitude,
                        longitude,
                        road_id
                    )
                )

            except Exception as e:

                print(
                    "Segment lookup error:",
                    e
                )

        # ----------------------------------------------------
        # AUTO-CREATE SEGMENTS
        # ----------------------------------------------------

        if (
            segment_number is None
            and road_id is not None
        ):

            print(
                "Segment not found/cached."
            )

            print(
                "Fetching OSM road geometry..."
            )

            try:

                xml_data = (
                    get_road_geometry(
                        road_id
                    )
                )

                if xml_data:

                    geometry = (
                        parse_road_geometry(
                            xml_data
                        )
                    )

                    if (
                        geometry
                        and len(geometry) >= 2
                    ):

                        segments = (
                            create_road_segments(
                                geometry
                            )
                        )

                        save_road_segments(
                            road_id,
                            osm_road_name,
                            segments
                        )

                        segment_number = (
                            find_nearest_segment(
                                latitude,
                                longitude,
                                road_id
                            )
                        )

                        print(
                            "Nearest segment after cache:",
                            segment_number
                        )

            except Exception as e:

                print(
                    "Auto segment creation error:",
                    e
                )

        print(
            "UPDATING SEGMENT:",
            segment_number
        )

        # ----------------------------------------------------
        # REVERSE GEOCODING
        # ----------------------------------------------------

        location = (
            get_location_details(
                latitude,
                longitude
            )
        )

        area = location.get(
            "area",
            "Unknown Area"
        )

        city = location.get(
            "city",
            "Unknown City"
        )

        state = location.get(
            "state",
            "Unknown State"
        )

        country = location.get(
            "country",
            "Unknown Country"
        )

        # OSM road name is preferred because it is directly
        # matched to the road.
        road_name = (
            osm_road_name
            if osm_road_name
            and osm_road_name != "Unknown Road"
            else location.get(
                "road_name",
                "Unknown Road"
            )
        )

        # ----------------------------------------------------
        # DATABASE
        # ----------------------------------------------------

        conn = get_db()

        cur = conn.cursor()

        # ----------------------------------------------------
        # STORE SENSOR RECORD
        # ----------------------------------------------------

        cur.execute(
            """
            INSERT INTO road_data
            (
                latitude,
                longitude,

                road_id,
                road_geometry,
                geometry_cached,

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
            VALUES (
                ?,?,?,?,?,
                ?,?,?,?,?,
                ?,?,
                ?,?,
                ?,?,
                ?,?,
                ?
            )
            """,
            (
                latitude,
                longitude,

                str(road_id)
                if road_id is not None
                else None,

                "",
                0,

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
            )
        )

        # ----------------------------------------------------
        # UPDATE ROAD SEGMENT HEALTH
        # ----------------------------------------------------

        if (
            segment_number is not None
            and road_id is not None
        ):

            cur.execute(
                """
                SELECT
                    average_health,
                    total_scans
                FROM road_segments
                WHERE
                    road_id = ?
                    AND segment_number = ?
                """,
                (
                    str(road_id),
                    segment_number
                )
            )

            segment_data = (
                cur.fetchone()
            )

            if segment_data:

                old_health = (
                    segment_data[0]
                    if segment_data[0] is not None
                    else 100.0
                )

                old_scans = (
                    segment_data[1]
                    if segment_data[1] is not None
                    else 0
                )

                new_scans = (
                    old_scans + 1
                )

                new_health = (
                    (
                        old_health
                        * old_scans
                    )
                    +
                    health_score
                ) / new_scans

                status = health_status(
                    new_health
                )

                # Remove emoji before storing
                # because database status should remain
                # clean text.
                clean_status = (
                    status
                    .replace("🟢", "")
                    .replace("🟡", "")
                    .replace("🟠", "")
                    .replace("🔴", "")
                    .strip()
                )

                # Get the existing health of this road segment
                cur.execute(
                    """
                    SELECT average_health, total_scans
                    FROM road_segments
                    WHERE road_id = ?
                      AND segment_number = ?
                    """,
                    (
                        str(road_id),
                        segment_number
                    )
                )

                existing_segment = cur.fetchone()

                if existing_segment:
                    old_health = float(existing_segment["average_health"])
                    old_scans = int(existing_segment["total_scans"])

                    # Keep the worse condition once damage has been detected
                    new_health = min(old_health, float(new_health))

                    new_scans = old_scans + 1

                    # Recalculate status from the retained health
                    if new_health >= 90:
                        clean_status = "Excellent"
                    elif new_health >= 80:
                        clean_status = "Good"
                    elif new_health >= 60:
                        clean_status = "Slight Damage"
                    elif new_health >= 40:
                        clean_status = "Moderate Damage"
                    elif new_health >= 20:
                        clean_status = "Poor"
                    else:
                        clean_status = "Critical"

                cur.execute(
                    """
                    UPDATE road_segments

                    SET
                        average_health = ?,
                        total_scans = ?,
                        status = ?,
                        last_update = ?

                    WHERE
                        road_id = ?
                        AND segment_number = ?
                    """,
                    (
                        new_health,
                        new_scans,
                        clean_status,
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        str(road_id),
                        segment_number
                    )
                )

                print(
                    f"[OK] Segment {segment_number} "
                    f"Health Updated: "
                    f"{round(new_health, 2)}% "
                    f"({clean_status})"
                )

            else:

                print(
                    "[WARN] Segment not found in database."
                )

        else:

            print(
                "[WARN] Segment number is None. "
                "Skipping segment health update."
            )

        conn.commit()

        conn.close()

        print(
            "[OK] Sensor Data Stored Successfully"
        )

        return jsonify({

            "status":
                "success",

            "message":
                "Data Stored Successfully",

            "latitude":
                latitude,

            "longitude":
                longitude,

            "road_id":
                road_id,

            "road_name":
                road_name,

            "area":
                area,

            "city":
                city,

            "state":
                state,

            "country":
                country,

            "segment_number":
                segment_number,

            "health_score":
                health_score,

            "road_health":
                road_health,

            "vibration":
                vibration
        })

    except Exception as e:

        print(
            "\n========== UPLOAD ERROR =========="
        )

        print(
            repr(e)
        )

        return jsonify({

            "status":
                "error",

            "message":
                str(e)
        }), 500


# ============================================================
# VIEW ALL DATABASE RECORDS
# ============================================================

@app.route(
    "/view"
)
def view():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM road_data
        ORDER BY id DESC
        """
    )

    rows = cur.fetchall()

    conn.close()

    return jsonify(
        [
            dict(row)
            for row in rows
        ]
    )


# ============================================================
# MAP DATA API
# ============================================================

@app.route(
    "/map_data"
)
def map_data():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            id,
            latitude,
            longitude,
            road_name,
            area,
            city,
            state,
            country,
            health_score,
            road_health,
            vibration,
            speed,
            timestamp

        FROM road_data

        WHERE
            latitude IS NOT NULL
            AND longitude IS NOT NULL
            AND latitude != 0
            AND longitude != 0

        ORDER BY id ASC

        LIMIT 500
        """
    )

    rows = cur.fetchall()

    conn.close()

    return jsonify(
        [
            dict(row)
            for row in rows
        ]
    )


# ============================================================
# OLD ROAD SEGMENTS ENDPOINT
# ============================================================

@app.route(
    "/road_segments"
)
def road_segments():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            road_id,
            road_geometry,
            health_score,
            road_health,
            road_name,
            area,
            city,
            speed,
            vibration,
            timestamp

        FROM road_data

        WHERE road_id IS NOT NULL

        GROUP BY road_id

        ORDER BY MAX(id) DESC

        LIMIT 100
        """
    )

    rows = cur.fetchall()

    conn.close()

    return jsonify(
        [
            dict(row)
            for row in rows
        ]
    )


# ============================================================
# CURVED OSM ROAD SEGMENTS API
# ============================================================

@app.route(
    "/api/road-segments"
)
def api_road_segments():

    latitude = request.args.get(
        "latitude",
        type=float
    )

    longitude = request.args.get(
        "longitude",
        type=float
    )

    radius_km = request.args.get(
        "radius",
        default=15.0,
        type=float
    )

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            road_id,
            road_name,
            segment_number,
            geometry,
            average_health,
            total_scans,
            status,
            last_update

        FROM road_segments

        WHERE total_scans > 0

        ORDER BY
            road_id,
            segment_number ASC
        """
    )

    rows = cur.fetchall()

    conn.close()

    segments = []

    maximum_distance = (
        radius_km * 1000
    )

    for row in rows:

        try:

            geometry = json.loads(
                row["geometry"]
            )

        except Exception:

            continue

        if (
            not geometry
            or len(geometry) < 2
        ):

            continue

        # ----------------------------------------------------
        # IMPORTANT FIX:
        #
        # Previously only geometry[0] was checked.
        #
        # For curved roads, the first point may be far away
        # even though another point in the same segment is
        # close to the phone.
        #
        # Now we check the minimum distance to ALL geometry
        # points.
        # ----------------------------------------------------

        if (
            latitude is not None
            and longitude is not None
        ):

            distance = (
                distance_to_geometry(
                    latitude,
                    longitude,
                    geometry
                )
            )

            if distance > maximum_distance:

                continue

        health = (
            row["average_health"]
            if row["average_health"] is not None
            else 100.0
        )

        status = health_status(
            health
        )

        segments.append({

            "road_id":
                row["road_id"],

            "road_name":
                row["road_name"]
                or "Unknown Road",

            "segment_number":
                row["segment_number"],

            "geometry":
                geometry,

            "average_health":
                round(
                    health,
                    2
                ),

            "total_scans":
                row["total_scans"]
                if row["total_scans"] is not None
                else 0,

            "status":
                row["status"]
                or status,

            "last_update":
                row["last_update"]
                or "Not yet scanned"
        })

    return jsonify(
        segments
    )


# ============================================================
# ROAD HEALTH AGGREGATION API
# ============================================================

@app.route(
    "/road_health_map"
)
def road_health_map():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            road_id,
            road_name,
            road_geometry,

            AVG(health_score)
                AS average_health,

            COUNT(*)
                AS total_scans,

            MAX(timestamp)
                AS last_update

        FROM road_data

        WHERE
            road_id IS NOT NULL

        GROUP BY road_id

        ORDER BY
            last_update DESC
        """
    )

    rows = cur.fetchall()

    conn.close()

    roads = []

    for row in rows:

        health = (
            row["average_health"]
            if row["average_health"] is not None
            else 100.0
        )

        geometry = []

        if row["road_geometry"]:

            try:

                geometry = json.loads(
                    row["road_geometry"]
                )

            except Exception:

                geometry = []

        roads.append({

            "road_id":
                row["road_id"],

            "road_name":
                row["road_name"]
                or "Unknown Road",

            "average_health":
                round(
                    health,
                    2
                ),

            "total_scans":
                row["total_scans"],

            "status":
                health_status(
                    health
                ),

            "last_update":
                row["last_update"],

            "geometry":
                geometry
        })

    return jsonify(
        roads
    )


# ============================================================
# LAST CACHED ROAD GEOMETRY
# ============================================================

@app.route(
    "/road_geometry"
)
def road_geometry():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            road_id,
            road_name,
            road_geometry,
            health_score,
            road_health

        FROM road_data

        WHERE
            geometry_cached = 1
            AND road_geometry IS NOT NULL
            AND road_geometry != ''

        ORDER BY id DESC

        LIMIT 1
        """
    )

    row = cur.fetchone()

    conn.close()

    if row is None:

        return jsonify({

            "status":
                "error",

            "message":
                "No road geometry found"
        })

    try:

        geometry = json.loads(
            row["road_geometry"]
        )

    except Exception:

        geometry = []

    return jsonify({

        "road_id":
            row["road_id"],

        "road_name":
            row["road_name"],

        "health_score":
            row["health_score"],

        "road_health":
            row["road_health"],

        "geometry":
            geometry
    })


# ============================================================
# MAP PAGE
# ============================================================

@app.route(
    "/map"
)
def road_map():

    return render_template(
        "map.html"
    )


# ============================================================
# CLEAR DATABASE
# ============================================================

@app.route(
    "/clear"
)
def clear():

    conn = get_db()

    cur = conn.cursor()

    cur.execute(
        "DELETE FROM road_data"
    )

    # Also clear cached segments.
    # Otherwise old road segments can remain visible
    # after road_data is cleared.

    cur.execute(
        "DELETE FROM road_segments"
    )

    conn.commit()

    conn.close()

    return jsonify({

        "status":
            "success",

        "message":
            "Road data and road segments cleared"
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/health"
)
def health_check():

    return jsonify({

        "status":
            "running",

        "server":
            "AI Road Assessment System",

        "database":
            DATABASE,

        "time":
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
    })


# ============================================================
# RUN FLASK
# ============================================================

if __name__ == "__main__":

    print(
        "\n=========================================="
    )

    print(
        "AI ROAD ASSESSMENT SYSTEM"
    )

    print(
        "=========================================="
    )

    print(
        "Database:",
        DATABASE
    )

    print(
        "Server:",
        "0.0.0.0:5000"
    )

    print(
        "==========================================\n"
    )

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )

