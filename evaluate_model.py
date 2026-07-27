import tensorflow as tf
import numpy as np

from tensorflow.keras.preprocessing.image import ImageDataGenerator
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report
)

# ==========================
# Load Model
# ==========================

model = tf.keras.models.load_model("road_condition_model.h5")

# ==========================
# Load Test Dataset
# ==========================

test_dir = "dataset_split/test"

test_datagen = ImageDataGenerator(rescale=1./255)

test_data = test_datagen.flow_from_directory(
    test_dir,
    target_size=(224,224),
    batch_size=32,
    class_mode="binary",
    shuffle=False
)

# ==========================
# Predict
# ==========================

predictions = model.predict(test_data)

predicted_classes = (predictions > 0.5).astype(int).flatten()

true_classes = test_data.classes

class_names = list(test_data.class_indices.keys())

# ==========================
# Metrics
# ==========================

accuracy = accuracy_score(true_classes, predicted_classes)

precision = precision_score(true_classes, predicted_classes)

recall = recall_score(true_classes, predicted_classes)

f1 = f1_score(true_classes, predicted_classes)

cm = confusion_matrix(true_classes, predicted_classes)

print("\n==============================")
print("ROAD CONDITION MODEL EVALUATION")
print("==============================\n")

print(f"Test Accuracy : {accuracy*100:.2f}%")
print(f"Precision     : {precision*100:.2f}%")
print(f"Recall        : {recall*100:.2f}%")
print(f"F1 Score      : {f1*100:.2f}%")

print("\n==============================")
print("CONFUSION MATRIX")
print("==============================")
print(cm)

print("\n==============================")
print("CLASSIFICATION REPORT")
print("==============================")
print(classification_report(
    true_classes,
    predicted_classes,
    target_names=class_names
))

print("\n==============================")
print("METRICS TABLE")
print("==============================")

print(f"""
+----------------+-----------+
| Metric         | Value     |
+----------------+-----------+
| Accuracy       | {accuracy*100:6.2f}% |
| Precision      | {precision*100:6.2f}% |
| Recall         | {recall*100:6.2f}% |
| F1 Score       | {f1*100:6.2f}% |
+----------------+-----------+
""")