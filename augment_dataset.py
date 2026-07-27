import os
import cv2
import random
import albumentations as A

# -----------------------------
# Paths
# -----------------------------
healthy_path = "dataset/Healthy_road"

# Target number of images
target_count = 13000

# -----------------------------
# Augmentation Pipeline
# -----------------------------
transform = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.RandomBrightnessContrast(p=0.5),
    A.Rotate(limit=15, p=0.5),
    A.GaussianBlur(p=0.3),
])

# Supported image formats
extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

images = [
    f for f in os.listdir(healthy_path)
    if f.lower().endswith(extensions)
]

current_count = len(images)

print(f"Current images: {current_count}")

while current_count < target_count:

    img_name = random.choice(images)

    img_path = os.path.join(healthy_path, img_name)

    image = cv2.imread(img_path)

    if image is None:
        continue

    augmented = transform(image=image)["image"]

    new_name = f"aug_{current_count}.jpg"

    cv2.imwrite(os.path.join(healthy_path, new_name), augmented)

    current_count += 1

    if current_count % 500 == 0:
        print(f"{current_count} images created")

print("Done!")
print(f"Final image count: {current_count}")