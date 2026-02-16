#!/bin/bash

# Генерируем код из openapi.yaml
~/go/bin/oapi-codegen -generate types,server,spec -package openapi ../../openapi/components/audit.yaml > internal/api/openapi/server.gen.go

echo "Код сгенерирован в internal/api/openapi/server.gen.go"