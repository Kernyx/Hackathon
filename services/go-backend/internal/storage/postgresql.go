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

// Модель события для PostgreSQL
type Event struct {
	ID        uint      `gorm:"primaryKey"`
	CreatedAt time.Time `gorm:"not null;default:now();index:idx_created_at,sort:desc"`

	EventType string     `gorm:"size:255;index"`
	Timestamp *time.Time `gorm:"index:idx_timestamp,sort:desc"`

	SourceAgentID   string          `gorm:"size:255;index"`
	SourceAgentName string          `gorm:"size:255"`
	SourceAgentMood json.RawMessage `gorm:"type:jsonb"`

	SourceAgentRelationships json.RawMessage `gorm:"type:jsonb"`
	SourceAgentActivity      json.RawMessage `gorm:"type:jsonb"`
	SourceAgentPlan          json.RawMessage `gorm:"type:jsonb"`

	TargetAgents json.RawMessage `gorm:"type:jsonb"`

	Message       *string `gorm:"type:text"`
	Tick          *int    `gorm:"index"`
	IsInitiative  *bool
	ActionResult  *string         `gorm:"type:text"`
	EventDataFull json.RawMessage `gorm:"type:jsonb;column:event_data"`

	SimulationContext json.RawMessage `gorm:"type:jsonb"`

	ProcessedAt time.Time `gorm:"not null;default:now()"`
	ProcessedTs int64
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
	sqlDB, err := p.db.DB()
	if err != nil {
		return err
	}
	return sqlDB.Ping()
}

func (p *PostgresStore) RunMigrations() error {
	err := p.db.AutoMigrate(&Event{})
	if err != nil {
		return fmt.Errorf("failed to migrate: %w", err)
	}
	log.Println("database migrations completed")
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

	result := p.db.CreateInBatches(dbEvents, 100)
	if result.Error != nil {
		return result.Error
	}

	log.Printf("batch saved %d events to PostgreSQL", result.RowsAffected)
	return nil
}

// Получить последние события
func (p *PostgresStore) GetRecentEvents(limit int) ([]*openapi.Event, error) {
	var dbEvents []Event
	result := p.db.Order("created_at DESC").Limit(limit).Find(&dbEvents)
	if result.Error != nil {
		return nil, result.Error
	}

	events := make([]*openapi.Event, 0, len(dbEvents))
	for _, dbEvent := range dbEvents {
		events = append(events, mapEventToOpenAPI(&dbEvent))
	}

	return events, nil
}

// Получить историю с пагинацией
func (p *PostgresStore) GetHistoryWithPagination(limit, offset int) ([]*openapi.Event, int64, error) {
	var dbEvents []Event
	var total int64

	p.db.Model(&Event{}).Count(&total)

	result := p.db.Order("created_at DESC").Limit(limit).Offset(offset).Find(&dbEvents)
	if result.Error != nil {
		return nil, 0, result.Error
	}

	events := make([]*openapi.Event, 0, len(dbEvents))
	for _, dbEvent := range dbEvents {
		events = append(events, mapEventToOpenAPI(&dbEvent))
	}

	return events, total, nil
}

// Поиск по типу события
func (p *PostgresStore) GetEventsByType(eventType string, limit int) ([]*openapi.Event, error) {
	var dbEvents []Event
	result := p.db.Where("event_type = ?", eventType).
		Order("created_at DESC").
		Limit(limit).
		Find(&dbEvents)

	if result.Error != nil {
		return nil, result.Error
	}

	events := make([]*openapi.Event, 0, len(dbEvents))
	for _, dbEvent := range dbEvents {
		events = append(events, mapEventToOpenAPI(&dbEvent))
	}

	return events, nil
}

// Маппинг из OpenAPI в БД модель
func mapOpenAPIToEvent(src *openapi.Event) *Event {
	e := &Event{
		ProcessedAt: time.Now().UTC(),
		ProcessedTs: time.Now().Unix(),
	}

	if src.EventType != nil {
		e.EventType = *src.EventType
	}

	if src.Timestamp != nil {
		t := src.Timestamp.UTC()
		e.Timestamp = &t
	}

	if src.SourceAgent != nil {
		if src.SourceAgent.AgentId != nil {
			e.SourceAgentID = *src.SourceAgent.AgentId
		}
		if src.SourceAgent.Name != nil {
			e.SourceAgentName = *src.SourceAgent.Name
		}

		if src.SourceAgent.Mood != nil {
			if moodJSON, err := json.Marshal(src.SourceAgent.Mood); err == nil {
				e.SourceAgentMood = moodJSON
			}
		}

		if src.SourceAgent.Relationships != nil {
			if relJSON, err := json.Marshal(src.SourceAgent.Relationships); err == nil {
				e.SourceAgentRelationships = relJSON
			}
		}

		if src.SourceAgent.Activity != nil {
			if actJSON, err := json.Marshal(src.SourceAgent.Activity); err == nil {
				e.SourceAgentActivity = actJSON
			}
		}

		if src.SourceAgent.Plan != nil {
			if planJSON, err := json.Marshal(src.SourceAgent.Plan); err == nil {
				e.SourceAgentPlan = planJSON
			}
		}
	}

	if src.TargetAgents != nil {
		if targetJSON, err := json.Marshal(src.TargetAgents); err == nil {
			e.TargetAgents = targetJSON
		}
	}

	if src.Data != nil {
		if src.Data.Message != nil {
			e.Message = src.Data.Message
		}
		if src.Data.Tick != nil {
			e.Tick = src.Data.Tick
		}
		if src.Data.IsInitiative != nil {
			e.IsInitiative = src.Data.IsInitiative
		}
		if src.Data.ActionResult != nil {
			e.ActionResult = src.Data.ActionResult
		}

		if dataJSON, err := json.Marshal(src.Data); err == nil {
			e.EventDataFull = dataJSON
		}
	}

	if src.SimulationContext != nil {
		if ctxJSON, err := json.Marshal(src.SimulationContext); err == nil {
			e.SimulationContext = ctxJSON
		}
	}

	if src.ProcessedAt != nil {
		e.ProcessedAt = src.ProcessedAt.UTC()
	}
	if src.ProcessedTs != nil {
		e.ProcessedTs = *src.ProcessedTs
	}

	return e
}

// Маппинг из БД модели в OpenAPI
func mapEventToOpenAPI(e *Event) *openapi.Event {
	event := &openapi.Event{
		EventType:   &e.EventType,
		Timestamp:   e.Timestamp,
		ProcessedAt: &e.ProcessedAt,
		ProcessedTs: &e.ProcessedTs,
	}

	sourceAgent := &openapi.SourceAgent{
		AgentId: &e.SourceAgentID,
		Name:    &e.SourceAgentName,
	}

	if len(e.SourceAgentMood) > 0 {
		var mood openapi.Mood
		if json.Unmarshal(e.SourceAgentMood, &mood) == nil {
			sourceAgent.Mood = &mood
		}
	}

	if len(e.SourceAgentRelationships) > 0 {
		var relationships map[string]openapi.Relationship
		if json.Unmarshal(e.SourceAgentRelationships, &relationships) == nil {
			sourceAgent.Relationships = &relationships
		}
	}

	if len(e.SourceAgentActivity) > 0 {
		var activity openapi.Activity
		if json.Unmarshal(e.SourceAgentActivity, &activity) == nil {
			sourceAgent.Activity = &activity
		}
	}

	if len(e.SourceAgentPlan) > 0 {
		var plan openapi.Plan
		if json.Unmarshal(e.SourceAgentPlan, &plan) == nil {
			sourceAgent.Plan = &plan
		}
	}

	event.SourceAgent = sourceAgent

	if len(e.TargetAgents) > 0 {
		var targets []openapi.TargetAgent
		if json.Unmarshal(e.TargetAgents, &targets) == nil {
			event.TargetAgents = &targets
		}
	}

	if len(e.EventDataFull) > 0 {
		var data openapi.EventData
		if json.Unmarshal(e.EventDataFull, &data) == nil {
			event.Data = &data
		}
	}

	if len(e.SimulationContext) > 0 {
		var ctx openapi.SimulationContext
		if json.Unmarshal(e.SimulationContext, &ctx) == nil {
			event.SimulationContext = &ctx
		}
	}

	return event
}
