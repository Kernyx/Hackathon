package processor

import (
	"audite-service/internal/api/openapi"
	"audite-service/internal/storage"
	"log"
	"time"
)

type EventProcessor struct {
	eventChan chan openapi.PostEventsJSONRequestBody
	store     *storage.RedisStore
}

func NewEventProcessor(eventChan chan openapi.PostEventsJSONRequestBody, store *storage.RedisStore) *EventProcessor {
	return &EventProcessor{
		eventChan: eventChan,
		store:     store,
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

	if err := p.store.SaveRecent(enrichedEvent); err != nil {
		return err
	}

	return nil
}
