// Package config loads environment-based settings for fleet-api.
package config

// File: internal/config/config.go
// Purpose: Centralized configuration parsing and derived helpers (DSN, Rabbit URL).

import (
	"fmt"
	"os"
	"strconv"
)

// ScaleConfig defines robot/job counts for a named fleet scale.
type ScaleConfig struct {
	Robots int
	Jobs   int
}

// ScaleMap defines the default scale presets.
var ScaleMap = map[string]ScaleConfig{
	"mini":  {Robots: 5, Jobs: 5},
	"small": {Robots: 5, Jobs: 25},
	"demo":  {Robots: 10, Jobs: 50},
	"large": {Robots: 20, Jobs: 100},
}

// Config stores parsed environment configuration for fleet-api.
type Config struct {
	Port             int
	DefaultScale     string
	DefaultSeed      int
	DefaultMode      string
	MySQLHost        string
	MySQLPort        string
	MySQLUser        string
	MySQLPassword    string
	MySQLDB          string
	RabbitHost       string
	RabbitPort       string
	RabbitUser       string
	RabbitPass       string
	ExchangeName     string
	GAReplanInterval int
}

// Load parses environment variables and returns a validated Config.
func Load() (*Config, error) {
	port, err := atoiWithDefault(os.Getenv("FLEET_API_PORT"), 8000)
	if err != nil {
		return nil, err
	}
	seed, err := atoiWithDefault(os.Getenv("FLEET_SEED"), 42)
	if err != nil {
		return nil, err
	}
	replan, err := atoiWithDefault(os.Getenv("GA_REPLAN_INTERVAL_S"), 0)
	if err != nil {
		return nil, err
	}
	overrideRobots, err := atoiWithDefault(os.Getenv("FLEET_ROBOTS"), 0)
	if err != nil {
		return nil, err
	}
	overrideJobs, err := atoiWithDefault(os.Getenv("FLEET_JOBS"), 0)
	if err != nil {
		return nil, err
	}

	if overrideRobots > 0 && overrideJobs > 0 {
		for key := range ScaleMap {
			ScaleMap[key] = ScaleConfig{Robots: overrideRobots, Jobs: overrideJobs}
		}
	}

	scale := getenv("FLEET_SCALE", "demo")
	if _, ok := ScaleMap[scale]; !ok {
		return nil, fmt.Errorf("invalid FLEET_SCALE: %s", scale)
	}

	mode := getenv("FLEET_MODE", "baseline")
	if mode != "baseline" && mode != "ga" {
		return nil, fmt.Errorf("invalid FLEET_MODE: %s", mode)
	}

	cfg := &Config{
		Port:             port,
		DefaultScale:     scale,
		DefaultSeed:      seed,
		DefaultMode:      mode,
		MySQLHost:        getenv("MYSQL_HOST", "mysql"),
		MySQLPort:        getenv("MYSQL_PORT", "3306"),
		MySQLUser:        getenv("MYSQL_USER", "amr"),
		MySQLPassword:    getenv("MYSQL_PASSWORD", "amrpass"),
		MySQLDB:          getenv("MYSQL_DB", "amr_fleet"),
		RabbitHost:       getenv("RABBITMQ_HOST", "rabbitmq"),
		RabbitPort:       getenv("RABBITMQ_PORT", "5672"),
		RabbitUser:       getenv("RABBITMQ_USER", "amr"),
		RabbitPass:       getenv("RABBITMQ_PASS", "amrpass"),
		ExchangeName:     "amr.events",
		GAReplanInterval: replan,
	}
	return cfg, nil
}

// DSN returns a MySQL DSN string based on the config.
func (c *Config) DSN() string {
	return fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?parseTime=true&multiStatements=true", c.MySQLUser, c.MySQLPassword, c.MySQLHost, c.MySQLPort, c.MySQLDB)
}

// RabbitURL returns the AMQP URL used by the publisher.
func (c *Config) RabbitURL() string {
	return fmt.Sprintf("amqp://%s:%s@%s:%s/", c.RabbitUser, c.RabbitPass, c.RabbitHost, c.RabbitPort)
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func atoiWithDefault(raw string, fallback int) (int, error) {
	if raw == "" {
		return fallback, nil
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		return 0, fmt.Errorf("invalid int %q: %w", raw, err)
	}
	return v, nil
}
