import os
import cv2
import shutil

# Dataset folders
classes = [
    "dataset/Cracked_road",
    "dataset/Healthy_road"
]

# Where blurred images will be moved
blur_folder = "blurred_images"

os.makedirs(blur_folder, exist_ok=True)

# Blur threshold
# Lower value = more blurry
THRESHOLD = 50


def check_blur(image_path):

    image = cv2.imread(image_path)

    if image is None:
        return True

    gray = cv2.cvtColor(
        image,
        cv2.COLOR_BGR2GRAY
    )

    # Calculate sharpness
    variance = cv2.Laplacian(
        gray,
        cv2.CV_64F
    ).var()

    return variance < THRESHOLD


for folder in classes:

    print("\nChecking:", folder)

    images = os.listdir(folder)

    removed = 0

    for img in images:

        path = os.path.join(
            folder,
            img
        )

        if img.lower().endswith(
            (".jpg",".jpeg",".png",".webp")
        ):

            if check_blur(path):

                destination = os.path.join(
                    blur_folder,
                    img
                )

                shutil.move(
                    path,
                    destination
                )

                removed += 1


    print(
        "Moved blurry images:",
        removed
    )


print("\nBlur checking completed!")