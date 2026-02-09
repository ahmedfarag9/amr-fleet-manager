SHELL := /bin/bash

up:
	docker compose up --build

down:
	docker compose down -v

logs:
	docker compose logs -f --tail=200

demo-baseline:
	curl -sS -X POST http://localhost:8080/api/runs \
		-H 'Content-Type: application/json' \
		-d '{"mode":"baseline"}' | jq

demo-ga:
	curl -sS -X POST http://localhost:8080/api/runs \
		-H 'Content-Type: application/json' \
		-d '{"mode":"ga"}' | jq
