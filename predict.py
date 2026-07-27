import tensorflow as tf
import numpy as np
from tensorflow.keras.preprocessing import image

# ==========================================
# Load Model (loads only once)
# ==========================================

model = tf.keras.models.load_model("road_condition_model.h5")


# ==========================================
# Analyze Road Function
# ==========================================

def analyze_road(img_path):

    # Load Image
    img = image.load_img(img_path, target_size=(224, 224))

    img_array = image.img_to_array(img)

    img_array = img_array / 255.0

    img_array = np.expand_dims(img_array, axis=0)

    # Predict

    prediction = model.predict(img_array, verbose=0)[0][0]

    # Determine class

    if prediction < 0.5:

        road_type = "Damaged Road"

        confidence = float((1 - prediction) * 100)

    else:

        road_type = "Healthy Road"

        confidence = float(prediction * 100)

    # Road assessment

    if road_type == "Damaged Road":

        health = "Poor"

        if confidence >= 99:

            severity = "Very High"

            recommendation = (
                "Immediate road repair is strongly recommended to prevent accidents."
            )

        elif confidence >= 95:

            severity = "High"

            recommendation = (
                "Road maintenance should be scheduled as soon as possible."
            )

        elif confidence >= 85:

            severity = "Moderate"

            recommendation = (
                "Road maintenance is recommended."
            )

        else:

            severity = "Low"

            recommendation = (
                "Monitor the road condition regularly."
            )

    else:

        health = "Good"

        severity = "None"

        recommendation = (
            "Road is in good condition. Routine monitoring is sufficient."
        )

    return {

        "prediction": road_type,

        "confidence": round(confidence, 2),

        "health": health,

        "severity": severity,

        "recommendation": recommendation

    }


# ==========================================
# Standalone Testing
# ==========================================

if __name__ == "__main__":

    img_path = input("Enter image path : ")

    result = analyze_road(img_path)

    print("\n========== ROAD ASSESSMENT ==========\n")

    print("Prediction      :", result["prediction"])

    print("Confidence      :", result["confidence"], "%")

    print("Road Health     :", result["health"])

    print("Severity        :", result["severity"])

    print("Recommendation  :", result["recommendation"])