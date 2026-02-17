package auth

import (
	"crypto/rsa"
	"crypto/x509"
	"encoding/pem"
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/golang-jwt/jwt/v5"
)

type Claims struct {
	Sub   string `json:"sub"`
	Scope string `json:"scope"`
	jwt.RegisteredClaims
}

var (
	ErrInvalidToken      = errors.New("invalid token")
	ErrUnexpectedMethod  = errors.New("unexpected signing method")
	ErrTokenExpired      = errors.New("token expired")
	ErrMissingAuthHeader = errors.New("missing authorization header")
	ErrInvalidAuthFormat = errors.New("invalid authorization format")
)

// Загружает ключ из файла ИЛИ переменной окружения
func LoadRSAPublicKey(publicKeyPath string) (*rsa.PublicKey, error) {
	var keyData []byte
	var err error

	if publicKeyPEM := os.Getenv("JWT_PUBLIC_KEY"); publicKeyPEM != "" {
		keyData = []byte(publicKeyPEM)
	} else {
		if !filepath.IsAbs(publicKeyPath) {
			cwd, err := os.Getwd()
			if err != nil {
				return nil, fmt.Errorf("failed to get working directory: %w", err)
			}
			publicKeyPath = filepath.Join(cwd, publicKeyPath)
		}

		keyData, err = os.ReadFile(publicKeyPath)
		if err != nil {
			return nil, fmt.Errorf("failed to read public key from %s: %w", publicKeyPath, err)
		}
	}

	block, _ := pem.Decode(keyData)
	if block == nil {
		return nil, errors.New("failed to decode PEM block containing public key")
	}

	pub, err := x509.ParsePKIXPublicKey(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("failed to parse public key: %w", err)
	}

	rsaPub, ok := pub.(*rsa.PublicKey)
	if !ok {
		return nil, errors.New("not an RSA public key")
	}

	return rsaPub, nil
}

// Валидирует JWT токен с RS256
func ValidateToken(tokenString string, publicKey *rsa.PublicKey) (*Claims, error) {
	token, err := jwt.ParseWithClaims(
		tokenString,
		&Claims{},
		func(token *jwt.Token) (interface{}, error) {
			if _, ok := token.Method.(*jwt.SigningMethodRSA); !ok {
				return nil, fmt.Errorf("%w: %v", ErrUnexpectedMethod, token.Header["alg"])
			}
			return publicKey, nil
		},
	)

	if err != nil {
		if errors.Is(err, jwt.ErrTokenExpired) {
			return nil, ErrTokenExpired
		}
		return nil, fmt.Errorf("failed to parse token: %w", err)
	}

	claims, ok := token.Claims.(*Claims)
	if !ok || !token.Valid {
		return nil, ErrInvalidToken
	}

	return claims, nil
}
