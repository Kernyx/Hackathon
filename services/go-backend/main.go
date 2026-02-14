package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
)

func main() {
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})
	
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("Go Backend - Ready!"))
	})
	
	port := os.Getenv("PORT")
	if port == "" {
		port = "8081"
	}
	
	fmt.Printf("✅ Go backend запущен на порту %s\n", port)
	
	if err := http.ListenAndServe(":"+port, nil); err != nil {
		log.Fatal(err)
	}
}
