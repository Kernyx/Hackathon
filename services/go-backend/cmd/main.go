package main

import (
	"audite-service/internal/api/openapi"
	"audite-service/internal/handlers"
	"audite-service/internal/processor"
	"audite-service/internal/storage"
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
	redisAddr := getEnv("REDIS_ADDR", "localhost:6379")
	redisPassword := getEnv("REDIS_PASSWORD", "")

	store := storage.NewRedisStore(redisAddr, redisPassword, 0)
	defer store.Close()

	if err := store.Ping(); err != nil {
		log.Fatalf("failed to connect to Redis: %v", err)
	}
	log.Println("Connected to Redis")

	eventChan := make(chan openapi.PostEventsJSONRequestBody, 1000)

	proc := processor.NewEventProcessor(eventChan, store)
	proc.Start()

	e := echo.New()

	e.Use(middleware.Logger())
	e.Use(middleware.Recover())
	e.Use(middleware.CORS())

	eventHandler := handlers.NewEventHandler(eventChan)
	feedHandler := handlers.NewFeedHandler(store)

	api := e.Group("/api/v1/audit")
	api.POST("/events", eventHandler.PostEvents)
	api.GET("/feed", feedHandler.GetFeed)

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
