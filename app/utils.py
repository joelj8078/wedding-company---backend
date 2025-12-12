import re

def sanitize_collection_name(name: str) -> str:
    """
    Produce a safe collection name from organization name.
    Allowed chars: a-z, 0-9, underscore, dash.
    Prefix with org_ to avoid collisions.
    """
    s = name.strip().lower()
    # replace any sequence of invalid chars with underscore
    s = re.sub(r"[^a-z0-9_-]+", "_", s)
    # reduce repeated underscores
    s = re.sub(r"_+", "_", s).strip("_")
    return f"org_{s}"
