import os
import random
import shutil

# -----------------------------
# Configuration
# -----------------------------
SOURCE_DIR = "dataset"
OUTPUT_DIR = "dataset_split"

TRAIN_RATIO = 0.70
VALID_RATIO = 0.20
TEST_RATIO = 0.10

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

random.seed(42)

# -----------------------------
# Create folders
# -----------------------------
for split in ["train", "valid", "test"]:
    for cls in ["Cracked_road", "Healthy_road"]:
        os.makedirs(os.path.join(OUTPUT_DIR, split, cls), exist_ok=True)

# -----------------------------
# Split each class
# -----------------------------
for cls in ["Cracked_road", "Healthy_road"]:

    class_path = os.path.join(SOURCE_DIR, cls)

    images = [
        f for f in os.listdir(class_path)
        if f.lower().endswith(IMAGE_EXTENSIONS)
    ]

    random.shuffle(images)

    total = len(images)

    train_end = int(total * TRAIN_RATIO)
    valid_end = train_end + int(total * VALID_RATIO)

    train_images = images[:train_end]
    valid_images = images[train_end:valid_end]
    test_images = images[valid_end:]

    splits = {
        "train": train_images,
        "valid": valid_images,
        "test": test_images
    }

    for split_name, file_list in splits.items():

        destination = os.path.join(OUTPUT_DIR, split_name, cls)

        for image in file_list:

            shutil.copy2(
                os.path.join(class_path, image),
                os.path.join(destination, image)
            )

    print(f"\n{cls}")
    print(f"Train : {len(train_images)}")
    print(f"Valid : {len(valid_images)}")
    print(f"Test  : {len(test_images)}")

print("\nDataset split completed successfully!")