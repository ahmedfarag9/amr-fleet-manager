// Package models defines request/response and DB model shapes.
package models

// File: internal/models/models.go
// Purpose: Shared data structures for runs and metrics.

import "time"

// Run models the runs table and API payloads.
type Run struct {
	ID           string     `json:"id"`
	Mode         string     `json:"mode"`
	Seed         int        `json:"seed"`
	Scale        string     `json:"scale"`
	RobotsCount  *int       `json:"robots_count,omitempty"`
	JobsCount    *int       `json:"jobs_count,omitempty"`
	ScenarioHash string     `json:"scenario_hash"`
	Status       string     `json:"status"`
	ErrorMessage *string    `json:"error_message,omitempty"`
	CreatedAt    time.Time  `json:"created_at"`
	StartedAt    time.Time  `json:"started_at"`
	CompletedAt  *time.Time `json:"completed_at,omitempty"`
}

// RunMetrics models the run_metrics table and API payloads.
type RunMetrics struct {
	RunID             string  `json:"run_id"`
	OnTimeRate        float64 `json:"on_time_rate"`
	TotalDistance     float64 `json:"total_distance"`
	AvgCompletionTime float64 `json:"avg_completion_time"`
	MaxLateness       float64 `json:"max_lateness"`
	CompletedJobs     int     `json:"completed_jobs"`
	FailedJobs        int     `json:"failed_jobs"`
	TotalJobs         int     `json:"total_jobs"`
}

// CreateRunRequest is the request payload for POST /runs.
type CreateRunRequest struct {
	Mode   string `json:"mode"`
	Seed   *int   `json:"seed,omitempty"`
	Scale  string `json:"scale,omitempty"`
	Robots *int   `json:"robots,omitempty"`
	Jobs   *int   `json:"jobs,omitempty"`
}

// CreateRunResponse is the response payload for POST /runs.
type CreateRunResponse struct {
	RunID  string `json:"run_id"`
	Mode   string `json:"mode"`
	Seed   int    `json:"seed"`
	Scale  string `json:"scale"`
	Robots *int   `json:"robots,omitempty"`
	Jobs   *int   `json:"jobs,omitempty"`
	Status string `json:"status"`
}

// CompareRunsResponse returns the latest baseline/GA metrics for a scenario.
type CompareRunsResponse struct {
	Seed     int         `json:"seed"`
	Scale    string      `json:"scale"`
	Robots   *int        `json:"robots,omitempty"`
	Jobs     *int        `json:"jobs,omitempty"`
	Baseline *RunMetrics `json:"baseline,omitempty"`
	GA       *RunMetrics `json:"ga,omitempty"`
}
