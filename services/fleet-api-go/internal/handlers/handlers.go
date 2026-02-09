// Package handlers wires HTTP routes to run service operations.
package handlers

// File: internal/handlers/handlers.go
// Purpose: HTTP handlers for /runs, /metrics, /compare, /health.

import (
	"encoding/json"
	"net/http"
	"strconv"

	"fleet-api-go/internal/models"
	"fleet-api-go/internal/services"
)

// Handler groups HTTP handlers for run operations.
type Handler struct {
	runs *services.RunService
}

// New returns a Handler wired to a RunService.
func New(runService *services.RunService) *Handler {
	return &Handler{runs: runService}
}

// Register attaches routes to the provided ServeMux.
func (h *Handler) Register(mux *http.ServeMux) {
	mux.HandleFunc("GET /health", h.health)
	mux.HandleFunc("POST /runs", h.createRun)
	mux.HandleFunc("GET /runs/{id}", h.getRun)
	mux.HandleFunc("GET /runs/{id}/metrics", h.getMetrics)
	mux.HandleFunc("GET /runs/compare", h.compareRuns)
}

func (h *Handler) health(w http.ResponseWriter, r *http.Request) {
	if err := h.runs.Health(r.Context()); err != nil {
		writeJSON(w, http.StatusServiceUnavailable, map[string]any{"status": "unhealthy", "error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"status": "ok"})
}

func (h *Handler) createRun(w http.ResponseWriter, r *http.Request) {
	var req models.CreateRunRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid JSON body"})
		return
	}
	resp, err := h.runs.CreateRun(r.Context(), req)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusCreated, resp)
}

func (h *Handler) getRun(w http.ResponseWriter, r *http.Request) {
	run, err := h.runs.GetRun(r.Context(), r.PathValue("id"))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	if run == nil {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": "run not found"})
		return
	}
	writeJSON(w, http.StatusOK, run)
}

func (h *Handler) getMetrics(w http.ResponseWriter, r *http.Request) {
	metrics, err := h.runs.GetMetrics(r.Context(), r.PathValue("id"))
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"error": err.Error()})
		return
	}
	if metrics == nil {
		writeJSON(w, http.StatusNotFound, map[string]any{"error": "metrics not found"})
		return
	}
	writeJSON(w, http.StatusOK, metrics)
}

func (h *Handler) compareRuns(w http.ResponseWriter, r *http.Request) {
	seedRaw := r.URL.Query().Get("seed")
	scale := r.URL.Query().Get("scale")
	if seedRaw == "" || scale == "" {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "seed and scale query params are required"})
		return
	}
	seed, err := strconv.Atoi(seedRaw)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid seed"})
		return
	}

	var robots *int
	var jobs *int

	if robotsRaw := r.URL.Query().Get("robots"); robotsRaw != "" {
		v, parseErr := strconv.Atoi(robotsRaw)
		if parseErr != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid robots"})
			return
		}
		robots = &v
	}
	if jobsRaw := r.URL.Query().Get("jobs"); jobsRaw != "" {
		v, parseErr := strconv.Atoi(jobsRaw)
		if parseErr != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid jobs"})
			return
		}
		jobs = &v
	}

	resp, err := h.runs.Compare(r.Context(), seed, scale, robots, jobs)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]any{"error": err.Error()})
		return
	}
	writeJSON(w, http.StatusOK, resp)
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
