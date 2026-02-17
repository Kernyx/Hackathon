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

	batchBuffer []*openapi.Event
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
		batchBuffer: make([]*openapi.Event, 0, 100),
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

func (p *EventProcessor) processEvent(req openapi.PostEventsJSONRequestBody) error {
	now := time.Now().UTC()
	ts := now.Unix()

	event := &openapi.Event{
		EventType:         req.EventType,
		SourceAgent:       req.SourceAgent,
		TargetAgents:      req.TargetAgents,
		Timestamp:         req.Timestamp,
		Data:              req.Data,
		SimulationContext: req.SimulationContext,
		ProcessedAt:       &now,
		ProcessedTs:       &ts,
	}

	if p.redisStore != nil {
		_ = p.redisStore.SaveRecent(event)
	}

	p.addToBatch(event)

	if p.hub != nil && p.hub.ClientCount() > 0 {
		if b, err := json.Marshal(event); err == nil {
			p.hub.Broadcast(b)
		}
	}

	eventTypeStr := "unknown"
	if req.EventType != nil {
		eventTypeStr = *req.EventType
	}
	log.Printf("Event processed: type=%s", eventTypeStr)
	return nil
}

func (p *EventProcessor) addToBatch(event *openapi.Event) {
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

	events := make([]*openapi.Event, len(p.batchBuffer))
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

func convertData(d *struct {
	Message string  `json:"message"`
	Mood    *string `json:"mood,omitempty"`
}) *struct {
	Message *string `json:"message,omitempty"`
	Mood    *string `json:"mood,omitempty"`
} {
	if d == nil {
		return nil
	}

	msg := d.Message

	return &struct {
		Message *string `json:"message,omitempty"`
		Mood    *string `json:"mood,omitempty"`
	}{
		Message: &msg,
		Mood:    d.Mood,
	}
}
