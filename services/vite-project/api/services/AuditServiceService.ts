/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AiAgent } from '../models/AiAgent';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AuditServiceService {
    /**
     * Publish AI log
     * @param requestBody
     * @returns any Event accepted
     * @throws ApiError
     */
    public static postAuditEvents(
        requestBody: {
            /**
             * Тип события для ML обработки
             */
            event_type?: string;
            /**
             * ИИ агент - инициатор общения
             */
            source_agent?: AiAgent;
            /**
             * ИИ агент(ы) - получатели сообщения
             */
            target_agents?: Array<AiAgent>;
            /**
             * Время события
             */
            timestamp?: string;
            /**
             * Данные события
             */
            data?: {
                /**
                 * Текст сообщения
                 */
                message: string;
                /**
                 * Настроение агента для ML обработки
                 */
                mood?: string;
            };
        },
    ): CancelablePromise<{
        status?: string;
        type?: string;
        timestamp?: string;
    }> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/audit/events',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Invalid request`,
                429: `Too many events`,
            },
        });
    }
}
