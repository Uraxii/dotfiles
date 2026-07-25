"""Django app registration for artifact review."""

from __future__ import annotations

from django.apps import AppConfig


class ArtifactReviewConfig(AppConfig):
    """Configure the artifact review Django app."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "artifact_review"


__all__ = ["ArtifactReviewConfig"]
