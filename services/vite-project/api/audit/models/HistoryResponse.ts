/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Event } from './Event';
export type HistoryResponse = {
    events?: Array<Event>;
    count?: number;
    limit?: number;
    offset?: number;
    /**
     * Общее количество событий в БД
     */
    total?: number;
    source?: string;
};

