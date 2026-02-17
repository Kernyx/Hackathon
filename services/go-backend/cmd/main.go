package main

import (
	"audite-service/internal/api/openapi"
	"audite-service/internal/handlers"
	"audite-service/internal/processor"
	"audite-service/internal/storage"
	"audite-service/internal/websocket"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"

	"github.com/labstack/echo/v4"
	"github.com/labstack/echo/v4/middleware"
)

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func main() {
	// redis
	redisAddr := getEnv("REDIS_ADDR", "localhost:6379")
	redisPassword := getEnv("REDIS_PASSWORD", "")

	redisStore := storage.NewRedisStore(redisAddr, redisPassword, 0)
	defer redisStore.Close()

	if err := redisStore.Ping(); err != nil {
		log.Fatalf("failed to connect to Redis: %v", err)
	}
	log.Println("Connected to Redis")

	// postgresql
	pgHost := getEnv("POSTGRES_HOST", "localhost")
	pgPort := getEnv("POSTGRES_PORT", "5432")
	pgUser := getEnv("POSTGRES_USER", "user")
	pgPassword := getEnv("POSTGRES_PASSWORD", "password")
	pgDB := getEnv("POSTGRES_DB", "audit")

	connStr := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		pgHost, pgPort, pgUser, pgPassword, pgDB)

	pgStore, err := storage.NewPostgresStore(connStr)
	if err != nil {
		log.Fatalf("failed to connect ot PostgreSQL: %v", err)
	}
	defer pgStore.Close()
	log.Println("Connected to PostgreSQL")

	if err := pgStore.RunMigrations(); err != nil {
		log.Fatalf("failed to run migration: %v", err)
	}

	// websocker hub
	hub := websocket.NewHub()
	go hub.Run()

	// event processor
	eventChan := make(chan openapi.PostEventsJSONRequestBody, 1000)

	proc := processor.NewEventProcessor(eventChan, redisStore, pgStore, hub)
	proc.Start()

	// http server
	e := echo.New()
	e.HidePort = true
	e.HideBanner = true

	e.Use(middleware.Logger())
	e.Use(middleware.Recover())
	e.Use(middleware.CORS())

	eventHandler := handlers.NewEventHandler(eventChan)
	feedHandler := handlers.NewFeedHandler(redisStore)
	wsHandler := handlers.NewWebSocketHandler(hub)

	api := e.Group("/api/v1/audit")
	api.POST("/events", eventHandler.PostEvents)
	api.GET("/feed", feedHandler.GetFeed)
	api.GET("/ws", wsHandler.ServeWS)
	api.GET("/ws/stats", wsHandler.GetStats)

	go func() {
		if err := e.Start(":8083"); err != nil {
			log.Printf("Server stopped: %v", err)
		}
	}()

	// Ожидаем сигнал завершения
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server...")
	close(eventChan)
}
