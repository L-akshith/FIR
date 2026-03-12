import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.applications.resnet50 import preprocess_input
import numpy as np
import matplotlib.pyplot as plt

# --- 1. CONFIGURATION ---
DATASET_DIR = "PHOTOS" # Make sure your folders are inside here (healthy, mahali, yellow_leaf)
IMG_HEIGHT = 224
IMG_WIDTH = 224
BATCH_SIZE = 32
EPOCHS = 20 # ResNet might benefit from a few more epochs

# --- 2. DATA PREPARATION ---
# Load training data
train_dataset = tf.keras.utils.image_dataset_from_directory(
    DATASET_DIR,
    validation_split=0.2,
    subset="training",
    seed=123,
    image_size=(IMG_HEIGHT, IMG_WIDTH),
    batch_size=BATCH_SIZE
)

# Load validation data
val_dataset = tf.keras.utils.image_dataset_from_directory(
    DATASET_DIR,
    validation_split=0.2,
    subset="validation",
    seed=123,
    image_size=(IMG_HEIGHT, IMG_WIDTH),
    batch_size=BATCH_SIZE
)

class_names = train_dataset.class_names
print(f"Classes detected: {class_names}")

# ResNet50 specific preprocessing function mapping
# ResNet expects BGR format and zero-centered color channels, not 0-1 scaling
def preprocess_for_resnet(images, labels):
    return preprocess_input(images), labels

train_dataset = train_dataset.map(preprocess_for_resnet)
val_dataset = val_dataset.map(preprocess_for_resnet)

# Data Augmentation
data_augmentation = tf.keras.Sequential([
  tf.keras.layers.RandomFlip('horizontal_and_vertical'),
  tf.keras.layers.RandomRotation(0.2),
  tf.keras.layers.RandomZoom(0.2),
])

# Prefetching for speed
AUTOTUNE = tf.data.AUTOTUNE
train_dataset = train_dataset.cache().shuffle(1000).prefetch(buffer_size=AUTOTUNE)
val_dataset = val_dataset.cache().prefetch(buffer_size=AUTOTUNE)

# --- 3. BUILD THE RESNET50 MODEL ---
# Load the ResNet50 model pre-trained on ImageNet
base_model = ResNet50(
    input_shape=(IMG_HEIGHT, IMG_WIDTH, 3),
    include_top=False, 
    weights='imagenet'
)

# Freeze the base model
base_model.trainable = False

# Build the final classification head
model = Sequential([
    data_augmentation,
    base_model,
    GlobalAveragePooling2D(),
    Dropout(0.3), # Slightly higher dropout for ResNet to prevent overfitting
    Dense(len(class_names), activation='softmax')
])

model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss=tf.keras.losses.SparseCategoricalCrossentropy(),
    metrics=['accuracy']
)

# --- 4. TRAIN THE MODEL ---
print("Starting training with ResNet50...")
history = model.fit(
    train_dataset,
    validation_data=val_dataset,
    epochs=EPOCHS
)

# Save the model
model.save("areca_resnet50_model.h5")
print("Model saved to areca_resnet50_model.h5")

# --- 5. PREDICTION FUNCTION ---
def predict_disease_resnet(image_path):
    # Load and resize
    img = tf.keras.utils.load_img(image_path, target_size=(IMG_HEIGHT, IMG_WIDTH))
    img_array = tf.keras.utils.img_to_array(img)
    
    # Expand dims and preprocess specifically for ResNet
    img_array = tf.expand_dims(img_array, 0)
    img_array = preprocess_input(img_array)

    # Predict
    predictions = model.predict(img_array)
    score = tf.nn.softmax(predictions[0])
    
    predicted_class = class_names[np.argmax(score)]
    confidence = 100 * np.max(score)
    
    print(f"Prediction: {predicted_class} | Confidence: {confidence:.2f}%")

# predict_disease_resnet("test_leaf.jpg")