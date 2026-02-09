CREATE DATABASE IF NOT EXISTS amr_fleet;
USE amr_fleet;

CREATE TABLE IF NOT EXISTS runs (
    id VARCHAR(64) PRIMARY KEY,
    mode ENUM('baseline','ga') NOT NULL,
    seed INT NOT NULL,
    scale ENUM('mini','small','demo','large') NOT NULL,
    robots_count INT NULL,
    jobs_count INT NULL,
    scenario_hash VARCHAR(128) NOT NULL,
    status ENUM('started','completed','failed') NOT NULL DEFAULT 'started',
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

CREATE TABLE IF NOT EXISTS run_metrics (
    run_id VARCHAR(64) PRIMARY KEY,
    on_time_rate DOUBLE NOT NULL,
    total_distance DOUBLE NOT NULL,
    avg_completion_time DOUBLE NOT NULL,
    max_lateness DOUBLE NOT NULL,
    completed_jobs INT NOT NULL,
    failed_jobs INT NOT NULL,
    total_jobs INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_run_metrics_run FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS jobs (
    id VARCHAR(64) NOT NULL,
    run_id VARCHAR(64) NOT NULL,
    pickup_x DOUBLE NOT NULL,
    pickup_y DOUBLE NOT NULL,
    dropoff_x DOUBLE NOT NULL,
    dropoff_y DOUBLE NOT NULL,
    deadline_ts INT NOT NULL,
    priority INT NOT NULL,
    state ENUM('pending','unassigned','assigned','in_progress','completed','failed') NOT NULL,
    assigned_robot_id INT NULL,
    created_sim_ts INT NOT NULL,
    started_sim_ts INT NULL,
    completed_sim_ts INT NULL,
    lateness_s DOUBLE NULL,
    PRIMARY KEY (id, run_id),
    CONSTRAINT fk_jobs_run FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS telemetry (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    robot_id INT NOT NULL,
    sim_time_s INT NOT NULL,
    x DOUBLE NOT NULL,
    y DOUBLE NOT NULL,
    battery DOUBLE NOT NULL,
    state VARCHAR(32) NOT NULL,
    current_job_id VARCHAR(64) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_telemetry_run FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS run_events (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(64) NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    routing_key VARCHAR(64) NOT NULL,
    payload_json JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_run_events_run FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE INDEX idx_telemetry_run_robot_ts ON telemetry (run_id, robot_id, sim_time_s);
CREATE INDEX idx_jobs_run_state_deadline ON jobs (run_id, state, deadline_ts);
CREATE INDEX idx_runs_status_created ON runs (status, created_at);
CREATE INDEX idx_run_metrics_created ON run_metrics (created_at);
