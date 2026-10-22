import os

# Settings require DB credentials at import time; tests mock the DB calls.
for key in ("CLEAN_DB_HOST", "CLEAN_DB_USER", "CLEAN_DB_PASSWORD", "CLEAN_DB_NAME"):
    os.environ.setdefault(key, "test")
