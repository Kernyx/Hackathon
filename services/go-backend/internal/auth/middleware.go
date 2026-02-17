package auth

import (
	"net/http"
	"strings"

	"github.com/labstack/echo/v4"
)

// JWTMiddleware создает middleware для проверки JWT токенов из header
func JWTMiddleware(secretKey []byte) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			// Получаем Authorization header
			authHeader := c.Request().Header.Get("Authorization")
			if authHeader == "" {
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "missing authorization header",
				})
			}

			// Проверяем формат "Bearer <token>"
			parts := strings.Split(authHeader, " ")
			if len(parts) != 2 || parts[0] != "Bearer" {
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "invalid authorization format, expected: Bearer <token>",
				})
			}

			tokenString := parts[1]

			// Валидируем токен
			claims, err := ValidateToken(tokenString, secretKey)
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

			// Сохраняем claims в контексте
			c.Set("user_id", claims.Sub)
			c.Set("claims", claims)

			return next(c)
		}
	}
}

// WSJWTMiddleware - middleware для WebSocket (читает JWT из query параметра)
func WSJWTMiddleware(secretKey []byte) echo.MiddlewareFunc {
	return func(next echo.HandlerFunc) echo.HandlerFunc {
		return func(c echo.Context) error {
			// Получаем токен из query параметра ?token=xxx
			tokenString := c.QueryParam("token")
			if tokenString == "" {
				return c.JSON(http.StatusUnauthorized, map[string]string{
					"error": "missing token query parameter",
				})
			}

			// Валидируем токен
			claims, err := ValidateToken(tokenString, secretKey)
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

			// Сохраняем claims в контексте для использования в handlers
			c.Set("user_id", claims.Sub)
			c.Set("claims", claims)

			return next(c)
		}
	}
}

// GetUserID - helper для получения user_id из контекста
func GetUserID(c echo.Context) (string, bool) {
	userID, ok := c.Get("user_id").(string)
	return userID, ok
}

// GetClaims - helper для получения claims из контекста
func GetClaims(c echo.Context) (*Claims, bool) {
	claims, ok := c.Get("claims").(*Claims)
	return claims, ok
}
