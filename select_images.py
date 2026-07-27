import os
import random
import shutil

random.seed(42)

SOURCE = "dataset_split"
DESTINATION = "annotation_dataset"

IMAGES_PER_CLASS = 2500

extensions = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

for split in ["train", "valid", "test"]:

    for cls in ["Cracked_road", "Healthy_road"]:

        src = os.path.join(SOURCE, split, cls)

        dst = os.path.join(DESTINATION, split, cls)

        os.makedirs(dst, exist_ok=True)

        images = [
            f for f in os.listdir(src)
            if f.lower().endswith(extensions)
        ]

        if len(images) > IMAGES_PER_CLASS:
            images = random.sample(images, IMAGES_PER_CLASS)

        for img in images:
            shutil.copy2(
                os.path.join(src, img),
                os.path.join(dst, img)
            )

        print(f"{split}/{cls}: {len(images)} images copied")

print("\nAnnotation dataset created successfully!")
