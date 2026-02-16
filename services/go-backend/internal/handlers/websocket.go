package handlers

import (
	"audite-service/internal/websocket"
	"log"
	"net/http"

	gorilla "github.com/gorilla/websocket"
	"github.com/labstack/echo/v4"
)

var upgrader = gorilla.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,

	CheckOrigin: func(r *http.Request) bool {
		return true
	},
}

type WebSocketHendler struct {
	hub *websocket.Hub
}

func NewWebSocketHandler(hub *websocket.Hub) *WebSocketHendler {
	return &WebSocketHendler{
		hub: hub,
	}
}

func (h *WebSocketHendler) ServeWS(c echo.Context) error {
	conn, err := upgrader.Upgrade(c.Response(), c.Request(), nil)
	if err != nil {
		log.Printf("WebSocket upgrade error: %v", err)
		return err
	}

	client := websocket.NewClient(h.hub, conn)
	h.hub.Register <- client

	go client.WritePump()
	go client.ReadPump()

	return nil
}

func (h *WebSocketHendler) GetStats(c echo.Context) error {
	return c.JSON(http.StatusOK, map[string]interface{}{
		"connected_clients": h.hub.ClientCount(),
	})
}
