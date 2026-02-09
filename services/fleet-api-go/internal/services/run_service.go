// Package services contains business logic for the fleet-api domain.
package services

// File: internal/services/run_service.go
// Purpose: Run orchestration (persist + publish run.started).

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"

	"fleet-api-go/internal/config"
	"fleet-api-go/internal/db"
	"fleet-api-go/internal/models"
	"fleet-api-go/internal/mq"
)

// RunService coordinates run creation and retrieval.
type RunService struct {
	cfg       *config.Config
	store     *db.Store
	publisher *mq.Publisher
}

// NewRunService constructs a RunService with dependencies.
func NewRunService(cfg *config.Config, store *db.Store, publisher *mq.Publisher) *RunService {
	return &RunService{cfg: cfg, store: store, publisher: publisher}
}

// CreateRun validates input, persists a run, and publishes run.started.
func (s *RunService) CreateRun(ctx context.Context, req models.CreateRunRequest) (*models.CreateRunResponse, error) {
	mode := req.Mode
	if mode == "" {
		mode = s.cfg.DefaultMode
	}
	if mode != "baseline" && mode != "ga" {
		return nil, fmt.Errorf("mode must be baseline or ga")
	}

	scale := req.Scale
	if scale == "" {
		scale = s.cfg.DefaultScale
	}
	if _, ok := config.ScaleMap[scale]; !ok {
		return nil, fmt.Errorf("invalid scale: %s", scale)
	}

	seed := s.cfg.DefaultSeed
	if req.Seed != nil {
		seed = *req.Seed
	}

	if (req.Robots == nil) != (req.Jobs == nil) {
		return nil, fmt.Errorf("robots and jobs overrides must be provided together")
	}
	if req.Robots != nil && *req.Robots <= 0 {
		return nil, fmt.Errorf("robots must be > 0")
	}
	if req.Jobs != nil && *req.Jobs <= 0 {
		return nil, fmt.Errorf("jobs must be > 0")
	}

	runID := uuid.NewString()
	run := models.Run{
		ID:           runID,
		Mode:         mode,
		Seed:         seed,
		Scale:        scale,
		RobotsCount:  req.Robots,
		JobsCount:    req.Jobs,
		ScenarioHash: "pending",
		Status:       "started",
	}
	if err := s.store.CreateRun(ctx, run); err != nil {
		return nil, err
	}

	event := map[string]any{
		"event_id":   uuid.NewString(),
		"event_type": "run.started",
		"run_id":     runID,
		"mode":       mode,
		"seed":       seed,
		"scale":      scale,
		"sim_time_s": 0,
	}
	if req.Robots != nil && req.Jobs != nil {
		event["robots"] = *req.Robots
		event["jobs"] = *req.Jobs
	}
	if err := s.publisher.Publish("run.started", event); err != nil {
		return nil, fmt.Errorf("publish run.started: %w", err)
	}

	return &models.CreateRunResponse{
		RunID:  runID,
		Mode:   mode,
		Seed:   seed,
		Scale:  scale,
		Robots: req.Robots,
		Jobs:   req.Jobs,
		Status: "started",
	}, nil
}

// GetRun fetches run metadata by ID.
func (s *RunService) GetRun(ctx context.Context, runID string) (*models.Run, error) {
	return s.store.GetRun(ctx, runID)
}

// GetMetrics fetches metrics for a run ID.
func (s *RunService) GetMetrics(ctx context.Context, runID string) (*models.RunMetrics, error) {
	return s.store.GetRunMetrics(ctx, runID)
}

// Compare fetches the latest completed baseline and GA metrics for a scenario.
func (s *RunService) Compare(ctx context.Context, seed int, scale string, robots *int, jobs *int) (*models.CompareRunsResponse, error) {
	if _, ok := config.ScaleMap[scale]; !ok {
		return nil, fmt.Errorf("invalid scale: %s", scale)
	}
	if (robots == nil) != (jobs == nil) {
		return nil, fmt.Errorf("robots and jobs compare filters must be provided together")
	}
	if robots != nil && *robots <= 0 {
		return nil, fmt.Errorf("robots must be > 0")
	}
	if jobs != nil && *jobs <= 0 {
		return nil, fmt.Errorf("jobs must be > 0")
	}

	baseline, err := s.store.GetLatestRunMetricsByMode(ctx, seed, scale, "baseline", robots, jobs)
	if err != nil {
		return nil, err
	}
	ga, err := s.store.GetLatestRunMetricsByMode(ctx, seed, scale, "ga", robots, jobs)
	if err != nil {
		return nil, err
	}
	return &models.CompareRunsResponse{
		Seed:     seed,
		Scale:    scale,
		Robots:   robots,
		Jobs:     jobs,
		Baseline: baseline,
		GA:       ga,
	}, nil
}

// Health checks database connectivity.
func (s *RunService) Health(ctx context.Context) error {
	ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	return s.store.Health(ctx)
}
