/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Event } from './Event';
export type EventsFeedResponse = {
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
     * Источник данных
     */
    source?: string;
};

