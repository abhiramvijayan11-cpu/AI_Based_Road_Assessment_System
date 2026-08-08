import requests
import json
import sqlite3
import xml.etree.ElementTree as ET
import math
import os

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

DATABASE = os.path.join(
    BASE_DIR,
    "data",
    "database.db"
)



# =====================================
# FIND NEAREST ROAD
# =====================================

def get_nearest_road(latitude, longitude):

    url = "https://nominatim.openstreetmap.org/reverse"


    params = {

        "lat": latitude,
        "lon": longitude,
        "format": "json",
        "zoom": 18

    }


    headers = {

        "User-Agent":
        "AI-Road-Assessment-System"

    }


    response = requests.get(
        url,
        params=params,
        headers=headers
    )


    data = response.json()


    print("\n===== OSM RESPONSE =====")
    print(data)


    osm_id = data.get("osm_id")


    # Extract road name from address first, then top-level name
    address = data.get("address", {})

    road_name = (
        address.get("road")
        or data.get("name")
        or "Unknown Road"
    )


    return {

        "road_id": osm_id,

        "road_name": road_name

    }




# =====================================
# GET ROAD GEOMETRY (raw XML)
# =====================================

def get_road_geometry(osm_id):


    if osm_id is None:

        return None



    url = (

        "https://api.openstreetmap.org/api/0.6/way/"

        + str(osm_id)

        + "/full"

    )



    response = requests.get(url)



    if response.status_code != 200:


        print(
            "Geometry request failed"
        )

        return None



    return response.text




# =====================================
# CONVERT OSM XML TO ROAD GEOMETRY
#
# Fix: respect the <way><nd ref=.../>
# ordering so the geometry follows the
# actual road direction instead of
# returning nodes in arbitrary order.
# =====================================

def parse_road_geometry(xml_data):


    try:

        root = ET.fromstring(xml_data)

        # ── 1. Build a dict of all nodes: id → [lat, lon]
        node_map = {}
        for node in root.findall("node"):
            nid  = node.attrib["id"]
            lat  = float(node.attrib["lat"])
            lon  = float(node.attrib["lon"])
            node_map[nid] = [lat, lon]

        # ── 2. Find the <way> element and read its nd refs in order
        way = root.find("way")
        if way is None:
            # fallback: return nodes in arbitrary order
            return list(node_map.values())

        geometry = []
        for nd in way.findall("nd"):
            ref = nd.attrib.get("ref")
            if ref and ref in node_map:
                geometry.append(node_map[ref])

        return geometry

    except Exception as e:

        print(
            "Geometry Parsing Error:",
            e
        )

        return []


# =====================================
# CREATE SEGMENTS FROM COMPLETE GEOMETRY
#
# Each consecutive pair of points is
# one segment, so curved roads are
# fully represented.
# =====================================

def create_road_segments(geometry):

    segments = []


    for i in range(len(geometry) - 1):

        segment = [

            geometry[i],

            geometry[i + 1]

        ]


        segments.append(segment)


    return segments


# =====================================
# SAVE ROAD SEGMENTS TO DATABASE
# =====================================

def save_road_segments(
        road_id,
        road_name,
        segments
):

    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()


    for index, segment in enumerate(segments):

        cur.execute(
        """
        INSERT INTO road_segments
        (
        road_id,
        road_name,
        segment_number,
        geometry,
        average_health,
        total_scans
        )

        VALUES(?,?,?,?,?,?)

        """,

        (

        str(road_id),

        road_name,

        index,

        json.dumps(segment),

        100,

        0

        ))


    conn.commit()

    conn.close()


    print(
    "[OK] Road segments saved:",
    len(segments)
    )


# ==========================================
# HAVERSINE DISTANCE
# ==========================================

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance in metres between two GPS points
    using the Haversine formula.
    """

    R = 6371000  # Earth radius in metres

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)


    a = (
        math.sin(dphi / 2) ** 2
        +
        math.cos(phi1)
        *
        math.cos(phi2)
        *
        math.sin(dlambda / 2) ** 2
    )


    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )


    return R * c


# ==========================================
# POINT-TO-SEGMENT PERPENDICULAR DISTANCE
#
# Returns the shortest distance from point P
# to the line segment (A→B).  Falls back to
# distance to the nearer endpoint when the
# perpendicular foot lies outside the segment.
# ==========================================

def _point_to_segment_distance(p_lat, p_lon, a_lat, a_lon, b_lat, b_lon):
    """
    Planar approximation (accurate enough for short road segments).
    Converts degrees to approximate metres using equirectangular.
    """
    # degrees → metres (equirectangular)
    cos_lat = math.cos(math.radians(p_lat))

    ax = a_lon * cos_lat * 111320.0
    ay = a_lat * 110540.0
    bx = b_lon * cos_lat * 111320.0
    by = b_lat * 110540.0
    px = p_lon * cos_lat * 111320.0
    py = p_lat * 110540.0

    dx = bx - ax
    dy = by - ay

    seg_len_sq = dx * dx + dy * dy

    if seg_len_sq == 0:
        # A and B are the same point
        return math.hypot(px - ax, py - ay)

    # Parameter t: projection of P onto AB
    t = ((px - ax) * dx + (py - ay) * dy) / seg_len_sq
    t = max(0.0, min(1.0, t))

    proj_x = ax + t * dx
    proj_y = ay + t * dy

    return math.hypot(px - proj_x, py - proj_y)


# ==========================================
# FIND NEAREST ROAD SEGMENT
#
# Changes vs. old version:
#   • Measures perpendicular distance to the
#     whole segment line (not just start point)
#   • Default tolerance raised to 75 m
#   • Returns only ONE nearest segment
# ==========================================

def find_nearest_segment(
        latitude,
        longitude,
        road_id,
        max_distance=75.0
):

    conn = sqlite3.connect(
        DATABASE
    )

    cur = conn.cursor()


    cur.execute(
    """
    SELECT
    segment_number,
    geometry

    FROM road_segments

    WHERE road_id=?

    """,
    (
        str(road_id),
    )
    )


    segments = cur.fetchall()


    conn.close()


    if not segments:

        return None



    nearest_segment  = None

    minimum_distance = float("inf")



    for segment in segments:

        segment_number = segment[0]

        geometry = json.loads(
            segment[1]
        )

        # Each stored segment is [start_point, end_point]
        # where each point is [lat, lon]
        a_lat, a_lon = geometry[0][0], geometry[0][1]
        b_lat, b_lon = geometry[1][0], geometry[1][1]

        distance = _point_to_segment_distance(
            latitude, longitude,
            a_lat,    a_lon,
            b_lat,    b_lon
        )


        if distance < minimum_distance:

            minimum_distance = distance

            nearest_segment = segment_number



    print("==============================")
    print(
        "Nearest Segment:",
        nearest_segment
    )

    print(
        "Distance:",
        round(minimum_distance, 2),
        "metres"
    )

    print("==============================")

    if minimum_distance > max_distance:
        print(
            f"[WARN] Segment distance {round(minimum_distance, 2)}m "
            f"exceeds max limit of {max_distance}m. Ignoring update."
        )
        return None

    return nearest_segment