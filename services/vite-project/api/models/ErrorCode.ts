/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Application specific error codes.
 * Prefixes: A - Authentication, S - Signup, L - Login, AT - Access Token, RT - Refresh Token, R - Authorization
 *
 */
export enum ErrorCode {
    /**
     * Internal error
     */
    INTERNAL_ERROR = 'A-1000',
    /**
     * Invalid signup credentials
     */
    INVALID_SIGNUP_CREDENTIALS = 'A-S1001',
    /**
     * Invalid login credentials
     */
    INVALID_LOGIN_CREDENTIALS = 'A-L1001',
    /**
     * Account banned
     */
    ACCOUNT_BANNED = 'A-L1002',
    /**
     * Too many login attempts
     */
    TOO_MANY_LOGIN_ATTEMPTS = 'A-L1003',
    /**
     * Access token expired
     */
    ACCESS_TOKEN_EXPIRED = 'A-AT1001',
    /**
     * Access token signature invalid
     */
    ACCESS_TOKEN_INVALID = 'A-AT1002',
    /**
     * Refresh token expired
     */
    REFRESH_TOKEN_EXPIRED = 'A-RT1001',
    /**
     * Refresh token invalid
     */
    REFRESH_TOKEN_INVALID = 'A-RT1002',
    /**
     * Insufficient permissions
     */
    INSUFFICIENT_PERMISSIONS = 'A-R1001',
    /**
     * Forbidden resource
     */
    FORBIDDEN_RESOURCE = 'A-R1002',
    /**
     * Role not allowed
     */
    ROLE_NOT_ALLOWED = 'A-R1003',
}
