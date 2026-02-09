from __future__ import annotations

"""
File: services/sim-runner-py/app/db.py
Purpose: MySQL helper functions for simulation persistence.
Key responsibilities:
- Update scenario hash and run status.
- Upsert jobs, insert telemetry, insert metrics.
"""

from contextlib import contextmanager
import os
from typing import Iterable

import pymysql


def _connect():
    """Open a new MySQL connection with dict cursor."""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "mysql"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "amr"),
        password=os.getenv("MYSQL_PASSWORD", "amrpass"),
        database=os.getenv("MYSQL_DB", "amr_fleet"),
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


@contextmanager
def db_cursor():
    """Context manager for a short-lived DB cursor."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def update_run_scenario_hash(run_id: str, scenario_hash: str) -> None:
    """Persist the scenario hash for a run."""
    with db_cursor() as cur:
        cur.execute("UPDATE runs SET scenario_hash=%s WHERE id=%s", (scenario_hash, run_id))


def upsert_job(run_id: str, job: dict) -> None:
    """Insert or update a job row for a run."""
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO jobs (id, run_id, pickup_x, pickup_y, dropoff_x, dropoff_y, deadline_ts, priority, state, assigned_robot_id, created_sim_ts, started_sim_ts, completed_sim_ts, lateness_s)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                state=VALUES(state),
                assigned_robot_id=VALUES(assigned_robot_id),
                started_sim_ts=VALUES(started_sim_ts),
                completed_sim_ts=VALUES(completed_sim_ts),
                lateness_s=VALUES(lateness_s)
            """,
            (
                job["id"],
                run_id,
                job["pickup_x"],
                job["pickup_y"],
                job["dropoff_x"],
                job["dropoff_y"],
                int(job["deadline_ts"]),
                int(job["priority"]),
                job["state"],
                job.get("assigned_robot_id"),
                int(job.get("created_sim_ts", 0)),
                job.get("started_sim_ts"),
                job.get("completed_sim_ts"),
                job.get("lateness_s", 0.0),
            ),
        )


def insert_telemetry_batch(run_id: str, rows: Iterable[dict]) -> None:
    """Bulk insert telemetry rows for a run."""
    rows = list(rows)
    if not rows:
        return
    with db_cursor() as cur:
        cur.executemany(
            """
            INSERT INTO telemetry (run_id, robot_id, sim_time_s, x, y, battery, state, current_job_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            [
                (
                    run_id,
                    int(row["robot_id"]),
                    int(row["sim_time_s"]),
                    float(row["x"]),
                    float(row["y"]),
                    float(row["battery"]),
                    row["state"],
                    row.get("current_job_id"),
                )
                for row in rows
            ],
        )


def insert_metrics(run_id: str, metrics: dict) -> None:
    """Insert or update run metrics."""
    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO run_metrics (run_id, on_time_rate, total_distance, avg_completion_time, max_lateness, completed_jobs, failed_jobs, total_jobs)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                on_time_rate=VALUES(on_time_rate),
                total_distance=VALUES(total_distance),
                avg_completion_time=VALUES(avg_completion_time),
                max_lateness=VALUES(max_lateness),
                completed_jobs=VALUES(completed_jobs),
                failed_jobs=VALUES(failed_jobs),
                total_jobs=VALUES(total_jobs)
            """,
            (
                run_id,
                float(metrics["on_time_rate"]),
                float(metrics["total_distance"]),
                float(metrics["avg_completion_time"]),
                float(metrics["max_lateness"]),
                int(metrics["completed_jobs"]),
                int(metrics["failed_jobs"]),
                int(metrics["total_jobs"]),
            ),
        )


def complete_run(run_id: str, status: str, error_message: str | None = None) -> None:
    """Mark a run completed or failed and persist error details if any."""
    with db_cursor() as cur:
        cur.execute(
            "UPDATE runs SET status=%s, error_message=%s, completed_at=UTC_TIMESTAMP() WHERE id=%s",
            (status, error_message, run_id),
        )
