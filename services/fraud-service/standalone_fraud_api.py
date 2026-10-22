"""Compatibility imports for the fraud service's historical test module.

The app is the same FastAPI application configured in :mod:`app.main`; there is
no parallel standalone detector or separate model implementation.
"""

from app.main import app
from app.ml.pipeline import FeaturePipeline as FeatureNormalizationPipeline
from app.ml.hybrid_engine import HybridFraudDetector as HybridFraudDetectionEngine

__all__ = ["app", "FeatureNormalizationPipeline", "HybridFraudDetectionEngine"]
