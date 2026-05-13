"""Provider registry — each provider is a tiny adapter around one upstream.

Every provider declares (category, source_id) and asks legal_guard to
validate itself at construction time.
"""
