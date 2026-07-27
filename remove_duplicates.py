import os
from PIL import Image
import imagehash

# Dataset folder
dataset_path = "dataset"

# Image extensions
extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

for class_name in os.listdir(dataset_path):

    class_path = os.path.join(dataset_path, class_name)

    if not os.path.isdir(class_path):
        continue

    print(f"\nChecking {class_name}...")

    hashes = {}
    duplicates = 0

    for filename in os.listdir(class_path):

        if not filename.lower().endswith(extensions):
            continue

        filepath = os.path.join(class_path, filename)

        try:
            img = Image.open(filepath)
            img_hash = imagehash.average_hash(img)

            if img_hash in hashes:
                os.remove(filepath)
                duplicates += 1
            else:
                hashes[img_hash] = filename

        except Exception:
            pass

    print(f"Removed {duplicates} duplicate images.")
    print(f"Remaining unique images: {len(hashes)}")

print("\nDuplicate removal completed!")