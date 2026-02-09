// Package main starts the fleet-api HTTP server and wires dependencies.
package main

// File: cmd/server/main.go
// Purpose: Process entrypoint for the fleet-api service.
// Key responsibilities:
// - Load config from environment.
// - Connect to MySQL and RabbitMQ.
// - Register HTTP routes and start the server.
// Key entrypoints: main()

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	httpx "fleet-api-go/internal/http"

	"fleet-api-go/internal/config"
	"fleet-api-go/internal/db"
	"fleet-api-go/internal/handlers"
	"fleet-api-go/internal/mq"
	"fleet-api-go/internal/services"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		log.Fatalf("load config: %v", err)
	}

	store, err := db.New(cfg.DSN())
	if err != nil {
		log.Fatalf("connect db: %v", err)
	}
	defer store.Close()

	publisher, err := mq.NewPublisher(cfg.RabbitURL(), cfg.ExchangeName)
	if err != nil {
		log.Fatalf("connect rabbitmq: %v", err)
	}
	defer publisher.Close()

	runService := services.NewRunService(cfg, store, publisher)
	h := handlers.New(runService)

	router := httpx.NewRouter(h.Register)
	server := &http.Server{
		Addr:         ":" + intToString(cfg.Port),
		Handler:      router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	go func() {
		log.Printf("fleet-api listening on %s", server.Addr)
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %v", err)
		}
	}()

	shutdownCh := make(chan os.Signal, 1)
	signal.Notify(shutdownCh, syscall.SIGINT, syscall.SIGTERM)
	<-shutdownCh

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := server.Shutdown(ctx); err != nil {
		log.Printf("shutdown error: %v", err)
	}
}

func intToString(v int) string {
	return fmt.Sprintf("%d", v)
}
