package auth

import (
	"crypto/rsa"
	"net/http"
	"strings"

	"github.com/labstack/echo/v4"
)

// Создает middleware для проверки JWT токенов из header
func JWTMiddleware(publicKey *rsa.PublicKey) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			authHeader := c.Request().Header.Get("Authorization")
			if authHeader == "" {
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "missing authorization header",
				})
			}

			parts := strings.Split(authHeader, " ")
			if len(parts) != 2 || parts[0] != "Bearer" {
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "invalid authorization format, expected: Bearer <token>",
				})
			}

			tokenString := parts[1]

			claims, err := ValidateToken(tokenString, publicKey)
			if err != nil {
				if err == ErrTokenExpired {
					return c.JSON(http.StatusUnauthorized, map[string]string{
						"error": "token expired",
					})
				}
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "invalid token",
				})
			}

			c.Set("user_id", claims.Sub)
			c.Set("claims", claims)

			return next(c)
		}
	}
}

// middleware для WebSocket (читает JWT из query параметра)
func WSJWTMiddleware(publicKey *rsa.PublicKey) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			tokenString := c.QueryParam("token")
			if tokenString == "" {
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "missing token query parameter",
				})
			}

			claims, err := ValidateToken(tokenString, publicKey)
			if err != nil {
				if err == ErrTokenExpired {
					return c.JSON(http.StatusUnauthorized, map[string]string{
						"error": "token expired",
					})
				}
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "invalid token",
				})
			}

			c.Set("user_id", claims.Sub)
			c.Set("claims", claims)

			return next(c)
		}
	}
}

// Опциональная проверка JWT (не блокирует запрос)
func OptionalJWTMiddleware(publicKey *rsa.PublicKey) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			authHeader := c.Request().Header.Get("Authorization")

			if authHeader != "" {
				parts := strings.Split(authHeader, " ")
				if len(parts) == 2 && parts[0] == "Bearer" {
					tokenString := parts[1]
					claims, err := ValidateToken(tokenString, publicKey)
					if err == nil {
						c.Set("user_id", claims.Sub)
						c.Set("claims", claims)
						c.Set("authenticated", true)
					}
				}
			}

			return next(c)
		}
	}
}

// helper для получения user_id из контекста
func GetUserID(c echo.Context) (string, bool) {
	userID, ok := c.Get("user_id").(string)
	return userID, ok
}

// helper для получения claims из контекста
func GetClaims(c echo.Context) (*Claims, bool) {
	claims, ok := c.Get("claims").(*Claims)
	return claims, ok
}
