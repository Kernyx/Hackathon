/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Event } from '../models/Event';
import type { EventAcceptedResponse } from '../models/EventAcceptedResponse';
import type { EventData } from '../models/EventData';
import type { EventsFeedResponse } from '../models/EventsFeedResponse';
import type { HistoryResponse } from '../models/HistoryResponse';
import type { SimulationContext } from '../models/SimulationContext';
import type { SourceAgent } from '../models/SourceAgent';
import type { TargetAgent } from '../models/TargetAgent';
import type { WebSocketStatsResponse } from '../models/WebSocketStatsResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuditServiceService {
    /**
     * Publish AI log
     * Отправить событие в систему аудита
     * @param requestBody
     * @returns EventAcceptedResponse Event accepted
     * @throws ApiError
     */
    public static postEvents(
        requestBody: {
            /**
             * Тип события
             */
            event_type: string;
            source_agent: SourceAgent;
            /**
             * Агенты-получатели
             */
            target_agents?: Array<TargetAgent>;
            /**
             * Время события
             */
            timestamp: string;
            data?: EventData;
            simulation_context?: SimulationContext;
        },
    ): CancelablePromise<EventAcceptedResponse> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/events',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Invalid request`,
                429: `Too many requests`,
            },
        });
    }
    /**
     * Get recent events feed (from Redis)
     * Получить последние события из Redis кеша
     * @param limit Количество событий (максимум 100)
     * @returns EventsFeedResponse List of recent events
     * @throws ApiError
     */
    public static getFeed(
        limit: number = 20,
    ): CancelablePromise<EventsFeedResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/feed',
            query: {
                'limit': limit,
            },
            errors: {
                500: `Internal server error`,
            },
        });
    }
    /**
     * Get historical events (from PostgreSQL)
     * Получить события по агенту из PostgreSQL
     * @param limit Количество событий (максимум 1000)
     * @param offset Смещение для пагинации
     * @returns HistoryResponse Historical events
     * @throws ApiError
     */
    public static getHistory(
        limit: number = 100,
        offset?: number,
    ): CancelablePromise<HistoryResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/history',
            query: {
                'limit': limit,
                'offset': offset,
            },
            errors: {
                500: `Internal server error`,
            },
        });
    }
    /**
     * Get events by agent ID
     * Получить события конкретного агента
     * @param agentId ID агента
     * @param limit Количество событий (максимум 500)
     * @returns any Agent events
     * @throws ApiError
     */
    public static getAgentsEvents(
        agentId: string,
        limit: number = 50,
    ): CancelablePromise<{
        events?: Array<Event>;
        /**
         * Количество возвращенных событий
         */
        count?: number;
        /**
         * Запрошенный лимит
         */
        limit?: number;
        /**
         * ID агента
         */
        agent_id?: string;
        source?: string;
    }> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/agents/{agent_id}/events',
            path: {
                'agent_id': agentId,
            },
            query: {
                'limit': limit,
            },
            errors: {
                400: `Invalid agent_id`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * Get agent statistics
     * Получить статистику по агенту
     * @param agentId ID агента
     * @returns any Agent statistics
     * @throws ApiError
     */
    public static getAgentsStats(
        agentId: string,
    ): CancelablePromise<{
        agent_id?: string;
        total_events?: number;
        messages_sent?: number;
        last_activity?: string;
        event_types?: Record<string, number>;
    }> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/agents/{agent_id}/stats',
            path: {
                'agent_id': agentId,
            },
            errors: {
                400: `Invalid agent_id`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * WebSocket connection
     * Подключение к WebSocket для real-time событий
     * @returns void
     * @throws ApiError
     */
    public static getWs(): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/ws',
            errors: {
                400: `Bad Request`,
            },
        });
    }
    /**
     * WebSocket statistics
     * Получить статистику WebSocket подключений
     * @returns WebSocketStatsResponse WebSocket stats
     * @throws ApiError
     */
    public static getWsStats(): CancelablePromise<WebSocketStatsResponse> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/ws/stats',
            errors: {
                500: `Internal server error`,
            },
        });
    }
}
