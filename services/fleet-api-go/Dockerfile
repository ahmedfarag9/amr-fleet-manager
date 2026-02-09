FROM golang:1.22 AS builder
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/fleet-api ./cmd/server

FROM alpine:3.20
RUN adduser -D appuser
WORKDIR /app
COPY --from=builder /out/fleet-api /app/fleet-api
USER appuser
EXPOSE 8000
ENTRYPOINT ["/app/fleet-api"]
