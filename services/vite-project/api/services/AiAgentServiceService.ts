/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PersonalityType } from '../models/PersonalityType';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class AiAgentServiceService {
    /**
     * Create AI agent
     * @param requestBody
     * @returns any AI Agent created
     * @throws ApiError
     */
    public static postAiAgents(
        requestBody: {
            username?: string;
            photo?: string;
            isMale?: boolean;
            age?: number;
            interests?: string;
            personalityType?: PersonalityType;
            additionalInformation?: string;
        },
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/ai-agents',
            body: requestBody,
            mediaType: 'application/json',
        });
    }
}
