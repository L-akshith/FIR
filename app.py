import tensorflow as tf
import numpy as np
from tensorflow.keras.applications.resnet50 import preprocess_input

# 1. Load the trained model
# Use "areca_resnet50_model.h5" if that is how it was saved
model = tf.keras.models.load_model("areca_resnet50_model.h5")

# 2. Define your class names 
# Keras automatically sorts folders alphabetically during training.
# Make sure this matches your exact folder names!
class_names = ['healthy', 'mahali', 'yellow_leaf'] 

def test_single_image(image_path):
    print(f"Analyzing {image_path}...")
    
    try:
        # 3. Load and resize the image to the 224x224 size ResNet expects
        img = tf.keras.utils.load_img(image_path, target_size=(224, 224))
        
        # 4. Convert the image to numbers and format it for ResNet50
        img_array = tf.keras.utils.img_to_array(img)
        img_array = tf.expand_dims(img_array, 0) # Make it a "batch" of 1 image
        img_array = preprocess_input(img_array)  # Apply ResNet's specific color shifts

        # 5. Make the prediction!
        predictions = model.predict(img_array)
        
        # 6. Calculate percentages
        score = tf.nn.softmax(predictions[0]) 
        predicted_class = class_names[np.argmax(score)]
        confidence = 100 * np.max(score)
        
        # 7. Print the results
        print("\n=== RESULTS ===")
        print(f"Diagnosis: {predicted_class.upper()}")
        print(f"Confidence: {confidence:.2f}%")
        print("===============\n")
        
    except FileNotFoundError:
        print(f"Error: Could not find the image at '{image_path}'. Please check the spelling.")

# --- RUN THE TEST ---
# Replace 'test_leaf.jpg' with the actual name of your image file
test_single_image("test/yellow leaf disease_original_92.jpg_c59b0773-27e9-4792-9bd0-1b55fcb2eaf0.jpg")