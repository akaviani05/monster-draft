"""Persistent worker controls shared by HTTP administration and the supervisor."""
import json


def worker_settings(db, default_slots=6):
    row = db.one("SELECT value FROM meta WHERE key='worker_settings'")
    return json.loads(row['value']) if row else {'slots': default_slots, 'paused': False}
