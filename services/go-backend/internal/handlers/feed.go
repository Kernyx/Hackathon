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
