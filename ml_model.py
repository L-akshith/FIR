"""
ArecaMitra Backend — ML Prediction Service
Wraps the existing EfficientNetB4 model for disease prediction.
"""

import numpy as np
import tensorflow as tf
from config import MODEL_PATH, IMG_SIZE

# ─── Singleton Model ───
_model = None


def load_model():
    """Load the trained model once (singleton pattern)."""
    global _model
    if _model is None:
        print(f"[ML] Loading model from {MODEL_PATH}...")
        _model = tf.keras.models.load_model(MODEL_PATH)
        print("[ML] Model loaded successfully.")
    return _model


# ─── Class Names (must match training folder order) ───
CLASS_NAMES = [
    "Healthy_Nut",
    "healthy_leaf",
    "mahali_kolerega",
    "yellow_leaf",
]

# ─── Normalization map for API output ───
DISPLAY_NAMES = {
    "Healthy_Nut": "healthy_nut",
    "healthy_leaf": "healthy_leaf",
    "mahali_kolerega": "koleroga",
    "yellow_leaf": "yellow_leaf",
}

HEALTHY_CLASSES = {"healthy_nut", "healthy_leaf"}


def _get_severity(confidence: float, disease: str) -> str | None:
    """Derive severity from confidence for diseased predictions."""
    if disease in HEALTHY_CLASSES:
        return None

    if confidence >= 0.85:
        return "severe"
    elif confidence >= 0.60:
        return "moderate"
    else:
        return "mild"


def predict_disease(image_path: str) -> dict:
    """
    Run disease prediction on an image.

    Args:
        image_path: Path to the uploaded image file.

    Returns:
        dict with keys: disease, confidence, severity
    """
    model = load_model()

    # Preprocess image
    img = tf.keras.utils.load_img(image_path, target_size=IMG_SIZE)
    img_array = tf.keras.utils.img_to_array(img)
    img_array = tf.expand_dims(img_array, 0)

    # Predict
    predictions = model.predict(img_array, verbose=0)[0]
    predicted_idx = int(np.argmax(predictions))
    raw_class = CLASS_NAMES[predicted_idx]
    confidence = float(np.max(predictions))

    # Normalize
    disease = DISPLAY_NAMES.get(raw_class, raw_class)
    severity = _get_severity(confidence, disease)

    # If healthy, collapse to single "healthy" label
    if disease in HEALTHY_CLASSES:
        disease = "healthy"

    return {
        "disease": disease,
        "confidence": round(confidence, 4),
        "severity": severity,
    }
