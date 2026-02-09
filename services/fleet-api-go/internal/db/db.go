// Package db wraps MySQL access for the fleet-api service.
package db

// File: internal/db/db.go
// Purpose: MySQL store implementation for runs and metrics.

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"

	"fleet-api-go/internal/models"
)

// Store wraps a sql.DB and exposes run/metrics queries.
type Store struct {
	db *sql.DB
}

// New opens a MySQL connection and verifies connectivity.
func New(dsn string) (*Store, error) {
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		return nil, fmt.Errorf("sql.Open: %w", err)
	}
	db.SetConnMaxLifetime(3 * time.Minute)
	db.SetMaxOpenConns(10)
	db.SetMaxIdleConns(10)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := db.PingContext(ctx); err != nil {
		return nil, fmt.Errorf("db ping: %w", err)
	}
	return &Store{db: db}, nil
}

// Close closes the underlying database connection.
func (s *Store) Close() error {
	return s.db.Close()
}

// Health performs a ping to validate database connectivity.
func (s *Store) Health(ctx context.Context) error {
	return s.db.PingContext(ctx)
}

// CreateRun inserts a new run row.
func (s *Store) CreateRun(ctx context.Context, run models.Run) error {
	query := `
		INSERT INTO runs (id, mode, seed, scale, robots_count, jobs_count, scenario_hash, status)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?)
	`
	_, err := s.db.ExecContext(
		ctx,
		query,
		run.ID,
		run.Mode,
		run.Seed,
		run.Scale,
		run.RobotsCount,
		run.JobsCount,
		run.ScenarioHash,
		run.Status,
	)
	if err != nil {
		return fmt.Errorf("insert run: %w", err)
	}
	return nil
}

// GetRun returns run metadata by ID.
func (s *Store) GetRun(ctx context.Context, runID string) (*models.Run, error) {
	query := `
		SELECT id, mode, seed, scale, robots_count, jobs_count, scenario_hash, status, error_message, created_at, started_at, completed_at
		FROM runs WHERE id = ?
	`
	var run models.Run
	if err := s.db.QueryRowContext(ctx, query, runID).Scan(
		&run.ID,
		&run.Mode,
		&run.Seed,
		&run.Scale,
		&run.RobotsCount,
		&run.JobsCount,
		&run.ScenarioHash,
		&run.Status,
		&run.ErrorMessage,
		&run.CreatedAt,
		&run.StartedAt,
		&run.CompletedAt,
	); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("select run: %w", err)
	}
	return &run, nil
}

// GetRunMetrics returns metrics for a run ID.
func (s *Store) GetRunMetrics(ctx context.Context, runID string) (*models.RunMetrics, error) {
	query := `
		SELECT run_id, on_time_rate, total_distance, avg_completion_time, max_lateness, completed_jobs, failed_jobs, total_jobs
		FROM run_metrics WHERE run_id = ?
	`
	var m models.RunMetrics
	if err := s.db.QueryRowContext(ctx, query, runID).Scan(
		&m.RunID,
		&m.OnTimeRate,
		&m.TotalDistance,
		&m.AvgCompletionTime,
		&m.MaxLateness,
		&m.CompletedJobs,
		&m.FailedJobs,
		&m.TotalJobs,
	); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("select run metrics: %w", err)
	}
	return &m, nil
}

// GetLatestRunMetricsByMode returns the most recent completed run metrics for a scenario and mode.
func (s *Store) GetLatestRunMetricsByMode(
	ctx context.Context,
	seed int,
	scale string,
	mode string,
	robots *int,
	jobs *int,
) (*models.RunMetrics, error) {
	var b strings.Builder
	b.WriteString(`
		SELECT rm.run_id, rm.on_time_rate, rm.total_distance, rm.avg_completion_time, rm.max_lateness, rm.completed_jobs, rm.failed_jobs, rm.total_jobs
		FROM run_metrics rm
		JOIN runs r ON r.id = rm.run_id
		WHERE r.seed = ? AND r.scale = ? AND r.mode = ? AND r.status = 'completed'
	`)
	args := []any{seed, scale, mode}
	if robots != nil && jobs != nil {
		b.WriteString(" AND r.robots_count = ? AND r.jobs_count = ?")
		args = append(args, *robots, *jobs)
	}
	b.WriteString(`
		ORDER BY r.completed_at DESC, r.created_at DESC
		LIMIT 1
	`)

	var m models.RunMetrics
	if err := s.db.QueryRowContext(ctx, b.String(), args...).Scan(
		&m.RunID,
		&m.OnTimeRate,
		&m.TotalDistance,
		&m.AvgCompletionTime,
		&m.MaxLateness,
		&m.CompletedJobs,
		&m.FailedJobs,
		&m.TotalJobs,
	); err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, nil
		}
		return nil, fmt.Errorf("select latest metrics: %w", err)
	}
	return &m, nil
}
