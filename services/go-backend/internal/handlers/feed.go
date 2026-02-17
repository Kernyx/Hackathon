package handlers

import (
	"audite-service/internal/storage"
	"net/http"
	"strconv"

	"github.com/labstack/echo/v4"
)

type FeedHandler struct {
	redisStore *storage.RedisStore
	pgStore    *storage.PostgresStore
}

func NewFeedHandler(redisStore *storage.RedisStore, pgStore *storage.PostgresStore) *FeedHandler {
	return &FeedHandler{
		redisStore: redisStore,
		pgStore:    pgStore,
	}
}

func (h *FeedHandler) GetFeed(c echo.Context) error {
	limitStr := c.QueryParam("limit")
	limit := int64(20)

	if limitStr != "" {
		if parsedLimit, err := strconv.ParseInt(limitStr, 10, 64); err == nil && parsedLimit > 0 {
			limit = parsedLimit

			if limit > 100 {
				limit = 100
			}
		}
	}

	events, err := h.redisStore.GetRecent(limit)
	if err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{
			"error": "failed to get feed",
		})
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"events": events,
		"count":  len(events),
		"limit":  limit,
		"source": "redis",
	})
}

func (h *FeedHandler) GetHistory(c echo.Context) error {
	limitStr := c.QueryParam("limit")
	limit := 100

	if limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit

			if limit > 1000 {
				limit = 1000
			}
		}
	}

	events, err := h.pgStore.GetRecentEvents(limit)
	if err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{
			"error": "failed to get history",
		})
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"events": events,
		"count":  len(events),
		"limit":  limit,
		"source": "postgresql",
	})
}

/*
func (h *FeedHandler) GetEventsByType(c echo.Context) error {
	eventType := c.Param("type")
	if eventType == "" {
		return c.JSON(http.StatusBadRequest, map[string]string{
			"error": "event_type is required",
		})
	}

	limitStr := c.QueryParam("limit")
	limit := 100
	if limitStr != "" {
		if parsedLimit, err := strconv.Atoi(limitStr); err == nil && parsedLimit > 0 {
			limit = parsedLimit
		}
	}

	events, err := h.pgStore.GetRecentEventsByType(eventType, limit)
	if err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{
			"error": "failed to get events by type",
		})
	}

	return c.JSON(http.StatusOK, map[string]interface{}{
		"events": events,
		"count":  len(events),
		"type":   eventType,
	})
}
*/
