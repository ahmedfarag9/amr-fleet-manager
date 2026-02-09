from __future__ import annotations

"""
File: services/dispatcher-worker-py/app/db.py
Purpose: MySQL connection helper (currently unused by dispatcher).
"""

import os
import pymysql


def connect_db():
    """Open a MySQL connection using environment settings."""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "amr"),
        password=os.getenv("MYSQL_PASSWORD", "amrpass"),
        database=os.getenv("MYSQL_DB", "amr_fleet"),
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )
