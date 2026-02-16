package processor

import (
	"audite-service/internal/api/openapi"
	"audite-service/internal/storage"
	"audite-service/internal/websocket"
	"encoding/json"
	"log"
	"sync"
	"time"
)

type EventProcessor struct {
	eventChan  chan openapi.PostEventsJSONRequestBody
	redisStore *storage.RedisStore
	pgStore    *storage.PostgresStore
	hub        *websocket.Hub

	batchBuffer []map[string]interface{}
	batchMutex  sync.Mutex
	batchTicker *time.Ticker
}

func NewEventProcessor(
	eventChan chan openapi.PostEventsJSONRequestBody,
	redisStore *storage.RedisStore,
	pgStore *storage.PostgresStore,
	hub *websocket.Hub,
) *EventProcessor {

	return &EventProcessor{
		eventChan:   eventChan,
		redisStore:  redisStore,
		pgStore:     pgStore,
		hub:         hub,
		batchBuffer: make([]map[string]interface{}, 0, 100),
		batchTicker: time.NewTicker(1 * time.Second),
	}
}

func (p *EventProcessor) Start() {
	go func() {
		log.Println("Event processor started")
		for event := range p.eventChan {
			if err := p.processEvent(event); err != nil {
				log.Printf("failed to process event: %v", err)
			}
		}
		log.Printf("Event processor stopped")
	}()

	go func() {
		log.Println("Batch inserted started (interval: 1s)")
		for range p.batchTicker.C {
			p.flushBatch()
		}
	}()
}

func (p *EventProcessor) Stop() {
	p.batchTicker.Stop()
	p.flushBatch()
	log.Println("Event processor and batch inserter stopped")
}

func (p *EventProcessor) processEvent(event openapi.PostEventsJSONRequestBody) error {
	enrichedEvent := map[string]interface{}{
		"event_type":    event.EventType,
		"source_agent":  event.SourceAgent,
		"target_agents": event.TargetAgents,
		"timestamp":     event.Timestamp,
		"data":          event.Data,
		"processed_at":  time.Now().Format(time.RFC3339),
		"processed_ts":  time.Now().Unix(),
	}

	if p.redisStore != nil {
		if err := p.redisStore.SaveRecent(enrichedEvent); err != nil {
			log.Printf("failed to save to Redis: %v", err)
		}
	}

	p.addToBatch(enrichedEvent)

	if p.hub != nil && p.hub.ClientCount() > 0 {
		messageBytes, err := json.Marshal(enrichedEvent)
		if err != nil {
			log.Printf("Failed to marshal event for WebSocket: %v", err)
		} else {
			p.hub.Broadcast(messageBytes)
			log.Printf("Event broadcasted to WebSocket clients")
		}
	}

	log.Printf("Event processed: type=%s", *event.EventType)
	return nil
}

func (p *EventProcessor) addToBatch(event map[string]interface{}) {
	p.batchMutex.Lock()
	defer p.batchMutex.Unlock()

	p.batchBuffer = append(p.batchBuffer, event)
	log.Printf("event added to batch buffer (size: %d)", len(p.batchBuffer))
}

func (p *EventProcessor) flushBatch() {
	p.batchMutex.Lock()

	if len(p.batchBuffer) == 0 {
		p.batchMutex.Unlock()
		return
	}

	events := make([]map[string]interface{}, len(p.batchBuffer))
	copy(events, p.batchBuffer)
	p.batchBuffer = p.batchBuffer[:0]

	p.batchMutex.Unlock()

	if p.pgStore != nil {
		log.Printf("flushing batch: %d events", len(events))
		if err := p.pgStore.BatchSaveEvents(events); err != nil {
			log.Printf("failed to batch save to PostgreSQL: %v", err)
		}
	}
}
