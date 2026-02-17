/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EventData = {
    /**
     * Текст сообщения
     */
    message?: string;
    /**
     * Номер тика симуляции
     */
    tick?: number;
    /**
     * Инициатор ли агент
     */
    is_initiative?: boolean;
    /**
     * Результат действия
     */
    action_result?: string;
    /**
     * Изменения в отношениях
     */
    sentiments?: Record<string, {
        delta?: number;
        reason?: string;
    }>;
};

