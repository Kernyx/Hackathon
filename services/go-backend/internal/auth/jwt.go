package auth

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"

	"github.com/golang-jwt/jwt/v5"
)

type Claims struct {
	Sub string `json:"sub"`
	jwt.RegisteredClaims
}

var (
	ErrInvalidToken      = errors.New("invalid token")
	ErrUnexpectedMethod  = errors.New("unexpected signing method")
	ErrTokenExpired      = errors.New("token expired")
	ErrMissingAuthHeader = errors.New("missing authorization header")
	ErrInvalidAuthFormat = errors.New("invalid authorization format")
)

// Загружает HS256 секретный ключ из файла
func LoadSecretKey(secretPath string) ([]byte, error) {
	if !filepath.IsAbs(secretPath) {
		cwd, err := os.Getwd()
		if err != nil {
			return nil, fmt.Errorf("failed to get working directory: %w", err)
		}
		secretPath = filepath.Join(cwd, secretPath)
	}

	key, err := os.ReadFile(secretPath)
	if err != nil {
		return nil, fmt.Errorf("failed to read secret key: %w", err)
	}

	key = []byte(string(key))
	if len(key) == 0 {
		return nil, errors.New("secret key is empty")
	}

	return key, nil
}

// Валидирует JWT токен с HS256
func ValidateToken(tokenString string, secretKey []byte) (*Claims, error) {
	token, err := jwt.ParseWithClaims(
		tokenString,
		&Claims{},
		func(token *jwt.Token) (interface{}, error) {
			if token.Method != jwt.SigningMethodHS256 {
				return nil, fmt.Errorf("%w: %v", ErrUnexpectedMethod, token.Header["alg"])
			}
			return secretKey, nil
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
