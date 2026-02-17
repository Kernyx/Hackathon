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

	if body.EventType == nil || *body.EventType == "" {
		return ctx.JSON(http.StatusBadRequest, map[string]string{
			"error": "event_type is required",
		})
	}

	if body.SourceAgent == nil {
		return ctx.JSON(http.StatusBadRequest, map[string]string{
			"error": "source_agent is required",
		})
	}

	if body.Timestamp == nil {
		return ctx.JSON(http.StatusBadRequest, map[string]string{
			"error": "timestamp is required",
		})
	}

	select {
	case h.eventChan <- body:

	default:
		return ctx.JSON(http.StatusTooManyRequests, map[string]string{
			"error": "too many events",
		})
	}

	now := time.Now()
	response := map[string]interface{}{
		"status":    "accepted",
		"type":      *body.EventType,
		"timestamp": now.Format(time.RFC3339),
	}

	return ctx.JSON(http.StatusAccepted, response)
}
