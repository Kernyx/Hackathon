package main

import (
	"audite-service/internal/api/openapi"
	"audite-service/internal/handlers"

	"github.com/labstack/echo/v4"
)

func main() {
	eventChan := make(chan openapi.PostEventsJSONRequestBody, 1000)

	e := echo.New()
	h := handlers.NewEventHandler(eventChan)

	openapi.RegisterHandlersWithBaseURL(e, h, "/api/v1/audit")

	e.Logger.Fatal(e.Start(":8083"))
}
