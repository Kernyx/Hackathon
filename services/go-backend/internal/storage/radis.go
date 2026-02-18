package storage

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/redis/go-redis/v9"
)

type RedisStore struct {
	client *redis.Client
	ctx    context.Context
}

func NewRedisStore(addr string, password string, db int) *RedisStore {
	client := redis.NewClient(&redis.Options{
		Addr:     addr,
		Password: password,
		DB:       db,
	})

	return &RedisStore{
		client: client,
		ctx:    context.Background(),
	}
}

func (r *RedisStore) Close() error {
	return r.client.Close()
}

func (r *RedisStore) Ping() error {
	return r.client.Ping(r.ctx).Err()
}

func (r *RedisStore) SaveRecent(event interface{}) error {
	eventJSON, err := json.Marshal(event)
	if err != nil {
		return fmt.Errorf("failed to marshal event: %w", err)
	}

	score := float64(time.Now().Unix())

	err = r.client.ZAdd(r.ctx, "recent_events", redis.Z{
		Score:  score,
		Member: string(eventJSON),
	}).Err()

	if err != nil {
		return fmt.Errorf("failed to save event to radis: %w", err)
	}

	r.client.ZRemRangeByRank(r.ctx, "recent_events", 0, -101)

	return nil
}

func (r *RedisStore) GetRecent(limit int64) ([]map[string]interface{}, error) {
	result, err := r.client.ZRange(r.ctx, "recent_events", 0, limit-1).Result()
	if err != nil {
		return nil, fmt.Errorf("failed to get events from redis: %w", err)
	}

	events := make([]map[string]interface{}, 0, len(result))
	for _, eventStr := range result {
		var event map[string]interface{}
		if err := json.Unmarshal([]byte(eventStr), &event); err != nil {

			continue
		}
		events = append(events, event)
	}

	return events, nil
}
