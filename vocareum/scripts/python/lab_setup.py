#!/usr/bin/env python3
"""Vocareum lab_setup.py — runs each time an attendee resumes the lab session.

Resumes the attendee's warehouse and returns the redirect URL to the entry notebook.
"""
import os
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "dbacademy", "-q"])

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _dbacademy_vs_patch  # noqa: F401  applies SDK name-sanitization

from dbacademy import voc_init

user = os.getenv("VOC_USER_EMAIL", "unknown@example.com")

print("=" * 60)
print(f"LAB SETUP (resume): {user}")
print("=" * 60)

db = voc_init()
redirect_url = db.user_setup_resume(user)

if redirect_url:
    print(f"Redirect URL: {redirect_url}")
    redirect_file = os.getenv("VOC_REDIRECT_FILE")
    if redirect_file:
        with open(redirect_file, "w") as f:
            f.write(redirect_url)

print("=" * 60)
print(f"LAB SETUP COMPLETE: {user}")
print("=" * 60)
