import requests


url = "http://127.0.0.1:5000/upload"


# Fake location 1
data1 = {

    "latitude": 9.9676839,

    "longitude": 76.3298908,

    "speed": 0.5,

    "vibration": 9.8,

    "health_score": 95,

    "road_health": "Excellent 🟢"

}


response = requests.post(
    url,
    json=data1
)


print("Location 1:")
print(response.json())





# Fake location 2

data2 = {

    "latitude": 9.9312,

    "longitude": 76.2673,

    "speed": 0.8,

    "vibration": 15.2,

    "health_score": 70,

    "road_health": "Moderate 🟡"

}



response = requests.post(
    url,
    json=data2
)


print("\nLocation 2:")
print(response.json())