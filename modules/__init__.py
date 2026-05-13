"""Module orchestration layer.

Each ``modules/<name>.py`` file picks the right provider from
``providers/<name>.py`` based on environment variables and falls back to
the free default when an upstream is unavailable.
"""
