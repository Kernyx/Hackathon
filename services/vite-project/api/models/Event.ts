/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EventData } from './EventData';
import type { SimulationContext } from './SimulationContext';
import type { SourceAgent } from './SourceAgent';
import type { TargetAgent } from './TargetAgent';
/**
 * Событие из ленты
 */
export type Event = {
    /**
     * Тип события
     */
    event_type?: string;
    source_agent?: SourceAgent;
    target_agents?: Array<TargetAgent>;
    /**
     * Время события
     */
    timestamp?: string;
    data?: EventData;
    simulation_context?: SimulationContext;
    /**
     * Время обработки события
     */
    processed_at?: string;
    /**
     * Unix timestamp обработки
     */
    processed_ts?: number;
};

