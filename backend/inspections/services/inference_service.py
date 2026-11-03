"""
AI Visual Quality Inspection Inference Service.
Integrates the official Round 2 BIT-PLATE-CV-1.0 computer vision classifier.
Guarantees exact preprocessing and feature extraction from the official Model package.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any

# Resolve paths to Model directory and classifier.npz
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
WORKSPACE_ROOT = BACKEND_DIR.parent
MODEL_DIR = WORKSPACE_ROOT / "Model"
CLASSIFIER_PATH = MODEL_DIR / "classifier.npz"

if not CLASSIFIER_PATH.exists():
    # Check alternate location inside backend if packaged there
    alt_path = BACKEND_DIR / "Model" / "classifier.npz"
    if alt_path.exists():
        MODEL_DIR = BACKEND_DIR / "Model"
        CLASSIFIER_PATH = alt_path

# Ensure Model directory is importable
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))

try:
    from inference import predict as official_predict, MODEL_VERSION
except ImportError:
    # Fallback to direct import
    import importlib.util
    spec = importlib.util.spec_from_file_location("official_inference", str(MODEL_DIR / "inference.py"))
    official_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(official_mod)
    official_predict = official_mod.predict
    MODEL_VERSION = official_mod.MODEL_VERSION


class InferenceService:
    """
    Singleton service wrapping the official Round 2 CV classifier.
    """
    def __init__(self, model_path: Path = CLASSIFIER_PATH):
        self.model_path = Path(model_path)
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Official classifier weights not found at: {self.model_path}. "
                "Ensure Model/classifier.npz is available in the workspace."
            )
        self.model_version = MODEL_VERSION

    def run_inference(self, image_path: str) -> Dict[str, Any]:
        """
        Runs genuine AI inference on a validated image.

        Args:
            image_path: Absolute or relative path to the saved image file on disk.

        Returns:
            Dict containing:
                - predicted_class: 'Normal' or 'Defective'
                - confidence: float (probability of predicted class)
                - defect_probability: float (probability of defect)
                - model_version: 'BIT-PLATE-CV-1.0'
        """
        path_obj = Path(image_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Inspection image file does not exist: {image_path}")

        try:
            result = official_predict(str(path_obj), model_path=str(self.model_path))
            return {
                "predicted_class": result["predicted_class"],
                "confidence": float(result["confidence"]),
                "defect_probability": float(result["defect_probability"]),
                "model_version": result.get("model_version", self.model_version),
            }
        except Exception as e:
            raise RuntimeError(f"AI inference failed on '{image_path}': {str(e)}") from e


# Export module-level singleton instance
inference_service = InferenceService()

