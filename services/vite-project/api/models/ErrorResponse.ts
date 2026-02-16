/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ErrorCode } from './ErrorCode';
export type ErrorResponse = {
    code: ErrorCode;
    /**
     * Human readable error message
     */
    message: string;
    /**
     * Error occurrence time
     */
    timestamp: string;
    /**
     * Unique identifier for log tracing
     */
    traceId?: string;
};

