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
     * @returns any Event published
     * @throws ApiError
     */
    public static postEvents(
        requestBody?: {
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
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/events',
            body: requestBody,
            mediaType: 'application/json',
        });
    }
}
