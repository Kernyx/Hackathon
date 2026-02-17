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

// Получить последние события из Redis
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

	response := map[string]interface{}{
		"events": events,
		"count":  len(events),
		"limit":  limit,
		"source": "redis",
	}

	return c.JSON(http.StatusOK, response)
}

// Получить события из PostgreSQL
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

	offsetStr := c.QueryParam("offset")
	offset := 0
	if offsetStr != "" {
		if parsedOffset, err := strconv.Atoi(offsetStr); err == nil && parsedOffset >= 0 {
			offset = parsedOffset
		}
	}

	events, total, err := h.pgStore.GetHistoryWithPagination(limit, offset)
	if err != nil {
		return c.JSON(http.StatusInternalServerError, map[string]string{
			"error": "failed to get history",
		})
	}

	response := map[string]interface{}{
		"events": events,
		"count":  len(events),
		"limit":  limit,
		"offset": offset,
		"total":  total,
		"source": "postgresql",
	}

	return c.JSON(http.StatusOK, response)
}
