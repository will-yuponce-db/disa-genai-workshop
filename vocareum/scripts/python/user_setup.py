#!/usr/bin/env python3
"""Vocareum user_setup.py — runs once per attendee on first lab entry.

Creates the attendee's Databricks user, copies notebooks into their workspace,
and emails them the sign-in link.
"""
import os
import subprocess
import sys

subprocess.check_call([sys.executable, "-m", "pip", "install", "dbacademy", "-q"])

from dbacademy import voc_init

user = os.getenv("VOC_USER_EMAIL", "unknown@example.com")

print("=" * 60)
print(f"USER SETUP: {user}")
print("=" * 60)

db = voc_init()
redirect_url = db.user_setup_create(user)

if redirect_url:
    print(f"Redirect URL: {redirect_url}")
    redirect_file = os.getenv("VOC_REDIRECT_FILE")
    if redirect_file:
        with open(redirect_file, "w") as f:
            f.write(redirect_url)

print("=" * 60)
print(f"USER SETUP COMPLETE: {user}")
print("=" * 60)
