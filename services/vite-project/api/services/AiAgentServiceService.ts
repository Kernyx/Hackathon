/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AiAgentDto } from '../models/AiAgentDto';
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
    public static postAiAgentAgents(
        requestBody: AiAgentDto,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/ai-agent/agents',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Incorrect credentials or bad request`,
                401: `Access token can't be updated or unauthorized access`,
            },
        });
    }
    /**
     * Get AI agent
     * @param agentId
     * @returns AiAgentDto Returns AI agent
     * @throws ApiError
     */
    public static getAiAgentAgents(
        agentId: string,
    ): CancelablePromise<AiAgentDto> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/ai-agent/agents/{agentId}',
            path: {
                'agentId': agentId,
            },
            errors: {
                400: `Incorrect credentials or bad request`,
                401: `Access token can't be updated or unauthorized access`,
            },
        });
    }
    /**
     * Update AI agent
     * @param agentId ID of the agent to update
     * @param requestBody
     * @returns any AI Agent updated successfully
     * @throws ApiError
     */
    public static putAiAgentAgents(
        agentId: string,
        requestBody: AiAgentDto,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'PUT',
            url: '/ai-agent/agents/{agentId}',
            path: {
                'agentId': agentId,
            },
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Incorrect credentials or bad request`,
                401: `Access token can't be updated or unauthorized access`,
            },
        });
    }
    /**
     * Delete AI agent
     * @param agentId
     * @returns void
     * @throws ApiError
     */
    public static deleteAiAgentAgents(
        agentId: string,
    ): CancelablePromise<void> {
        return __request(OpenAPI, {
            method: 'DELETE',
            url: '/ai-agent/agents/{agentId}',
            path: {
                'agentId': agentId,
            },
            errors: {
                400: `Incorrect credentials or bad request`,
                401: `Access token can't be updated or unauthorized access`,
            },
        });
    }
    /**
     * Get agents related with user
     * @param userId
     * @returns AiAgentDto List of agents related to user
     * @throws ApiError
     */
    public static getAiAgentUsersAgents(
        userId: string,
    ): CancelablePromise<Array<AiAgentDto>> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/ai-agent/users/{userId}/agents',
            path: {
                'userId': userId,
            },
            errors: {
                400: `Incorrect credentials or bad request`,
                401: `Access token can't be updated or unauthorized access`,
            },
        });
    }
    /**
     * Get relations for user
     * @param userId ID of the user
     * @returns any List of agent relations
     * @throws ApiError
     */
    public static getAiAgentUsersAgentsRelations(
        userId: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/ai-agent/users/{userId}/agents/relations',
            path: {
                'userId': userId,
            },
            errors: {
                400: `Incorrect credentials or bad request`,
                401: `Access token can't be updated or unauthorized access`,
            },
        });
    }
}
