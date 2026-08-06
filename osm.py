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
        "zoom":18

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


    data=response.json()


    print("\n===== OSM RESPONSE =====")

    print(data)



    osm_id=data.get("osm_id")


    road_name=data.get(
        "name",
        "Unknown Road"
    )


    return {


        "road_id":osm_id,

        "road_name":road_name


    }




# =====================================
# GET ROAD GEOMETRY
# =====================================

def get_road_geometry(osm_id):


    if osm_id is None:

        return None



    url = (

        "https://api.openstreetmap.org/api/0.6/way/"

        + str(osm_id)

        + "/full"

    )



    response=requests.get(url)



    if response.status_code != 200:


        print(
            "Geometry request failed"
        )

        return None



    return response.text





# =====================================
# CONVERT OSM XML TO ROAD GEOMETRY
# =====================================

def parse_road_geometry(xml_data):


    try:

        root = ET.fromstring(xml_data)


        geometry = []


        for node in root.findall("node"):


            lat = float(
                node.attrib["lat"]
            )


            lon = float(
                node.attrib["lon"]
            )


            geometry.append(
                [
                    lat,
                    lon
                ]
            )



        return geometry



    except Exception as e:

        print(
            "Geometry Parsing Error:",
            e
        )


        return []

def create_road_segments(geometry):

    segments = []


    for i in range(len(geometry)-1):

        segment = [

            geometry[i],

            geometry[i+1]

        ]


        segments.append(segment)


    return segments
def save_road_segments(
        road_id,
        road_name,
        segments
):

    import sqlite3
    import json

    DATABASE = r"C:\AI_Based_Road_Assessment_System\data\database.db"


    conn = sqlite3.connect(DATABASE)

    cur = conn.cursor()


    for index,segment in enumerate(segments):

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
    "✓ Road segments saved:",
    len(segments)
    )

# ==========================================
# FIND NEAREST ROAD SEGMENT
# ==========================================

def calculate_distance(lat1, lon1, lat2, lon2):

    """
    Calculate distance between two GPS points
    """

    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    dphi = math.radians(lat2-lat1)
    dlambda = math.radians(lon2-lon1)


    a = (
        math.sin(dphi/2)**2
        +
        math.cos(phi1)
        *
        math.cos(phi2)
        *
        math.sin(dlambda/2)**2
    )


    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1-a)
    )


    return R*c



def find_nearest_segment(
        latitude,
        longitude,
        road_id
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



    nearest_segment = None

    minimum_distance = float("inf")



    for segment in segments:


        segment_number = segment[0]

        geometry = json.loads(
            segment[1]
        )


        # segment start point

        seg_lat = geometry[0][0]

        seg_lon = geometry[0][1]


        distance = calculate_distance(
            latitude,
            longitude,
            seg_lat,
            seg_lon
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
        round(minimum_distance,2),
        "meters"
    )

    print("==============================")


    return nearest_segment