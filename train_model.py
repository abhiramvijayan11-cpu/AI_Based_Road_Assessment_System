import tensorflow as tf

from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import MobileNetV2
from tensorflow.keras.layers import Dense, Dropout, GlobalAveragePooling2D
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam

from tensorflow.keras.callbacks import (
    EarlyStopping,
    ReduceLROnPlateau,
    ModelCheckpoint
)


# ==========================
# Dataset paths
# ==========================

train_dir = "dataset_split/train"
valid_dir = "dataset_split/valid"


IMG_SIZE = 224
BATCH_SIZE = 32


# ==========================
# Data augmentation
# ==========================

train_datagen = ImageDataGenerator(

    rescale=1./255,

    rotation_range=25,

    width_shift_range=0.15,

    height_shift_range=0.15,

    zoom_range=0.25,

    shear_range=0.15,

    horizontal_flip=True,

    brightness_range=[0.7,1.3]

)


valid_datagen = ImageDataGenerator(
    rescale=1./255
)



train_data = train_datagen.flow_from_directory(

    train_dir,

    target_size=(IMG_SIZE,IMG_SIZE),

    batch_size=BATCH_SIZE,

    class_mode="binary"

)


valid_data = valid_datagen.flow_from_directory(

    valid_dir,

    target_size=(IMG_SIZE,IMG_SIZE),

    batch_size=BATCH_SIZE,

    class_mode="binary"

)



print(train_data.class_indices)



# ==========================
# MobileNetV2
# ==========================


base_model = MobileNetV2(

    weights="imagenet",

    include_top=False,

    input_shape=(224,224,3)

)


# Initially freeze

base_model.trainable = False



x = base_model.output

x = GlobalAveragePooling2D()(x)

x = Dropout(0.4)(x)


output = Dense(

    1,

    activation="sigmoid"

)(x)



model = Model(

    base_model.input,

    output

)



model.compile(

    optimizer=Adam(
        learning_rate=0.0001
    ),

    loss="binary_crossentropy",

    metrics=["accuracy"]

)



# ==========================
# First training stage
# ==========================


callbacks=[

EarlyStopping(

monitor="val_loss",

patience=5,

restore_best_weights=True

),


ReduceLROnPlateau(

monitor="val_loss",

factor=0.2,

patience=3

),


ModelCheckpoint(

"best_road_model.h5",

monitor="val_accuracy",

save_best_only=True

)

]



history=model.fit(

    train_data,

    validation_data=valid_data,

    epochs=15,

    callbacks=callbacks

)



# ==========================
# Fine tuning stage
# ==========================


print("Starting fine tuning...")


base_model.trainable=True


# Freeze first 100 layers

for layer in base_model.layers[:100]:

    layer.trainable=False



model.compile(

    optimizer=Adam(

        learning_rate=0.00001

    ),

    loss="binary_crossentropy",

    metrics=["accuracy"]

)



history_fine=model.fit(

    train_data,

    validation_data=valid_data,

    epochs=15,

    callbacks=callbacks

)



# Save final model


model.save(

"road_condition_model.h5"

)


print("Training completed successfully")