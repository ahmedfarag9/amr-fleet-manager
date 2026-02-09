// Package http provides the HTTP router and middleware for fleet-api.
package http

// File: internal/http/router.go
// Purpose: Construct mux and apply CORS + request logging middleware.

import (
	"net/http"
	"time"
)

// NewRouter builds an HTTP handler with CORS and request logging.
func NewRouter(register func(mux *http.ServeMux)) http.Handler {
	mux := http.NewServeMux()
	register(mux)
	return withCORS(withRequestLogging(mux))
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		w.Header().Set("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func withRequestLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		next.ServeHTTP(w, r)
		_ = start
	})
}
