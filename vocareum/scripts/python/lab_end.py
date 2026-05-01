#!/usr/bin/env python3
"""Vocareum lab_end.py — runs when an attendee finishes or times out.

Stops the attendee's warehouse to save costs. Notebooks remain in their workspace.
"""
import os
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "dbacademy", "-q"])

from dbacademy import voc_init

user = os.getenv("VOC_USER_EMAIL", "unknown@example.com")

print("=" * 60)
print(f"LAB END: {user}")
print("=" * 60)

db = voc_init()
db.user_setup_pause(user)

print("=" * 60)
print(f"LAB END COMPLETE: {user}")
print("=" * 60)
