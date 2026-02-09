// Package mq provides RabbitMQ publishing utilities.
package mq

// File: internal/mq/publisher.go
// Purpose: Publish domain events to the amr.events exchange.

import (
	"encoding/json"
	"fmt"
	"time"

	"github.com/streadway/amqp"
)

// Publisher wraps an AMQP connection/channel for event publishing.
type Publisher struct {
	conn     *amqp.Connection
	channel  *amqp.Channel
	exchange string
}

// NewPublisher connects to RabbitMQ and declares the exchange.
func NewPublisher(url, exchange string) (*Publisher, error) {
	conn, err := amqp.Dial(url)
	if err != nil {
		return nil, fmt.Errorf("amqp dial: %w", err)
	}
	ch, err := conn.Channel()
	if err != nil {
		_ = conn.Close()
		return nil, fmt.Errorf("amqp channel: %w", err)
	}
	if err := ch.ExchangeDeclare(exchange, "topic", true, false, false, false, nil); err != nil {
		_ = ch.Close()
		_ = conn.Close()
		return nil, fmt.Errorf("declare exchange: %w", err)
	}
	return &Publisher{conn: conn, channel: ch, exchange: exchange}, nil
}

// Close closes the AMQP channel and connection.
func (p *Publisher) Close() {
	if p.channel != nil {
		_ = p.channel.Close()
	}
	if p.conn != nil {
		_ = p.conn.Close()
	}
}

// Publish emits a JSON event to the configured exchange.
func (p *Publisher) Publish(routingKey string, payload map[string]any) error {
	payload["routing_key"] = routingKey
	payload["ts_utc"] = time.Now().UTC().Format(time.RFC3339Nano)
	body, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal event: %w", err)
	}
	return p.channel.Publish(
		p.exchange,
		routingKey,
		false,
		false,
		amqp.Publishing{
			ContentType:  "application/json",
			DeliveryMode: amqp.Persistent,
			Body:         body,
		},
	)
}
