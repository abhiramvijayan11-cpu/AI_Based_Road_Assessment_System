import os

dataset_path = "dataset"  # Replace with the path to your dataset directory
for class_name in os.listdir(dataset_path):
    class_path = os.path.join(dataset_path, class_name)

    if os.path.isdir(class_path):
        image_count = 0

        for file in os.listdir(class_path):
            if file.lower().endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
                image_count += 1

        print(f"{class_name}: {image_count} images")