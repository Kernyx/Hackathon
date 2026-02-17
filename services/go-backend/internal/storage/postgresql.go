package storage

import (
	"audite-service/internal/api/openapi"
	"encoding/json"
	"fmt"
	"log"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

type Event struct {
	ID                  uint            `gorm:"primaryKey"`
	EventType           string          `gorm:"size:255;index"`
	SourceAgentID       *string         `gorm:"type:uuid;index"`
	SourceAgentUsername *string         `gorm:"size:255"`
	Timestamp           *time.Time      `gorm:"index:idx_timestamp,sort:desc"`
	Message             *string         `gorm:"type:text"`
	Mood                *string         `gorm:"size:50"`
	TargetAgents        json.RawMessage `gorm:"type:jsonb"`
	Data                json.RawMessage `gorm:"type:jsonb"`
	ProcessedAt         time.Time       `gorm:"not null;default:now()"`
	CreatedAt           time.Time       `gorm:"not null;default:now();index:idx_created_at,sort:desc"`
}

func (Event) TableName() string {
	return "events"
}

type PostgresStore struct {
	db *gorm.DB
}

func NewPostgresStore(connStr string) (*PostgresStore, error) {
	db, err := gorm.Open(postgres.Open(connStr), &gorm.Config{
		Logger: logger.Default.LogMode(logger.Info),
		NowFunc: func() time.Time {
			return time.Now().UTC()
		},
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect to postgres: %w", err)
	}

	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}
	sqlDB.SetMaxOpenConns(25)
	sqlDB.SetMaxIdleConns(5)
	sqlDB.SetConnMaxLifetime(5 * time.Minute)

	return &PostgresStore{db: db}, nil
}

func (p *PostgresStore) Close() error {
	sqlDB, err := p.db.DB()
	if err != nil {
		return nil
	}
	return sqlDB.Close()
}

func (p *PostgresStore) Ping() error {
	err := p.db.AutoMigrate(&Event{})
	if err != nil {
		return fmt.Errorf("failed to migration: %w", err)
	}

	log.Printf("Database migration completed")
	return nil
}

func (p *PostgresStore) RunMigrations() error {
	err := p.db.AutoMigrate(&Event{})
	if err != nil {
		return fmt.Errorf("failed to migrate: %w", err)
	}
	log.Println("Database migrations completed")
	return nil
}

func (p *PostgresStore) SaveEvent(ev *openapi.Event) error {
	return p.db.Create(mapOpenAPIToEvent(ev)).Error
}

func (p *PostgresStore) BatchSaveEvents(events []*openapi.Event) error {
	if len(events) == 0 {
		return nil
	}

	dbEvents := make([]*Event, 0, len(events))
	for _, e := range events {
		dbEvents = append(dbEvents, mapOpenAPIToEvent(e))
	}

	return p.db.CreateInBatches(dbEvents, 100).Error
}

func (p *PostgresStore) GetRecentEvents(limit int) ([]map[string]interface{}, error) {
	var events []Event
	result := p.db.Order("created_at DESC").Limit(limit).Find(&events)
	if result.Error != nil {
		return nil, result.Error
	}

	eventMaps := make([]map[string]interface{}, 0, len(events))
	for _, event := range events {
		eventMap := map[string]interface{}{
			"event_type":   event.EventType,
			"processed_at": event.ProcessedAt.Format(time.RFC3339),
			"created_at":   event.CreatedAt.Format(time.RFC3339),
		}

		if event.SourceAgentID != nil {
			eventMap["source_agent_id"] = *event.SourceAgentID
		}
		if event.SourceAgentUsername != nil {
			eventMap["source_agent_username"] = *event.SourceAgentUsername
		}
		if event.Timestamp != nil {
			eventMap["timestamp"] = event.Timestamp.Format(time.RFC3339)
		}
		if event.Message != nil {
			eventMap["message"] = *event.Message
		}
		if event.Mood != nil {
			eventMap["mood"] = *event.Mood
		}
		if len(event.TargetAgents) > 0 {
			var targets interface{}
			json.Unmarshal(event.TargetAgents, &targets)
			eventMap["target_agents"] = targets
		}
		if len(event.Data) > 0 {
			var data interface{}
			json.Unmarshal(event.Data, &data)
			eventMap["data"] = data
		}

		eventMaps = append(eventMaps, eventMap)
	}

	return eventMaps, nil
}

func mapOpenAPIToEvent(src *openapi.Event) *Event {
	e := &Event{
		ProcessedAt: time.Now().UTC(),
	}

	if src.EventType != nil {
		e.EventType = *src.EventType
	}

	if src.SourceAgent != nil {
		id := src.SourceAgent.Id.String()
		username := src.SourceAgent.Username

		e.SourceAgentID = &id
		e.SourceAgentUsername = &username
	}

	if src.Timestamp != nil {
		t := src.Timestamp.UTC()
		e.Timestamp = &t
	}

	if src.Data != nil {

		if src.Data.Message != nil {
			e.Message = src.Data.Message
		}

		if src.Data.Mood != nil {
			e.Mood = src.Data.Mood
		}

		if b, err := json.Marshal(src.Data); err == nil {
			e.Data = b
		}
	}

	if src.TargetAgents != nil {
		if b, err := json.Marshal(src.TargetAgents); err == nil {
			e.TargetAgents = b
		}
	}

	if src.ProcessedAt != nil {
		e.ProcessedAt = src.ProcessedAt.UTC()
	}

	return e
}
