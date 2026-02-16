/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class DefaultService {
    /**
     * Sign up
     * @param requestBody
     * @returns any User successfully registered
     * @throws ApiError
     */
    public static postSignup(
        requestBody: {
            username: string;
            email: string;
            password: string;
        },
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/signup',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Incorrect credentials`,
                409: `User already registered`,
                429: `Too many requests`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * Sign in
     * @param requestBody
     * @returns any User authenticated
     * @throws ApiError
     */
    public static postSignin(
        requestBody: {
            email: string;
            password: string;
        },
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'POST',
            url: '/signin',
            body: requestBody,
            mediaType: 'application/json',
            errors: {
                400: `Incorrect credentials`,
                429: `Too many requests`,
                500: `Internal server error`,
            },
        });
    }
    /**
     * Refresh access token
     * @param refreshToken Refresh token required to update access token
     * @returns any Access token updated
     * @throws ApiError
     */
    public static getRefreshToken(
        refreshToken: string,
    ): CancelablePromise<any> {
        return __request(OpenAPI, {
            method: 'GET',
            url: '/refresh-token',
            cookies: {
                'refreshToken': refreshToken,
            },
            errors: {
                401: `Access token can't be updated. Sign-in required`,
                429: `Too many requests`,
                500: `Internal server error`,
            },
        });
    }
}
