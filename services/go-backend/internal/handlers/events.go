package handlers

import (
	"audite-service/internal/api/openapi"
	"net/http"
	"time"

	"github.com/labstack/echo/v4"
)

type EventHandler struct {
	eventChan chan openapi.PostEventsJSONRequestBody
}

func NewEventHandler(eventChan chan openapi.PostEventsJSONRequestBody) *EventHandler {
	return &EventHandler{
		eventChan: eventChan,
	}
}

func (h *EventHandler) PostEvents(ctx echo.Context) error {
	var body openapi.PostEventsJSONRequestBody
	if err := ctx.Bind(&body); err != nil {
		return ctx.JSON(http.StatusBadRequest, map[string]string{
			"error": "invalid json",
		})
	}

	select {
	case h.eventChan <- body:
	default:
		return ctx.JSON(http.StatusTooManyRequests, map[string]string{
			"error": "too many events",
		})
	}

	return ctx.JSON(http.StatusAccepted, map[string]interface{}{
		"status": "accepted",
		"type":   body.EventType,
		"time":   time.Now(),
	})
}

func generateID() string {
	return "evt_" + time.Now().Format("20060102150405")
}
