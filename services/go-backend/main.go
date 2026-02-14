package main

import (
	"fmt"
	"log"
	"net/http"
)

func main() {
	http.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Write([]byte("OK"))
	})

	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/html")
		w.Write([]byte(`
			<!DOCTYPE html>
			<html>
			<head>
				<title>Go Backend</title>
				<style>
					body { font-family: Arial; text-align: center; padding: 50px; }
					h1 { color: #3498db; }
				</style>
			</head>
			<body>
				<h1>✅ Go Backend работает!</h1>
				<p>Порт: 8081</p>
			</body>
			</html>
		`))
	})

	port := "8081"
	fmt.Printf("Go backend запущен на порту %s\n", port)
	log.Fatal(http.ListenAndServe("0.0.0.0:"+port, nil))
}
