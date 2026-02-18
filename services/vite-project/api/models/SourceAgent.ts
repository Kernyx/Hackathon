/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { Activity } from './Activity';
import type { Mood } from './Mood';
import type { Plan } from './Plan';
import type { Relationship } from './Relationship';
export type SourceAgent = {
    agent_id: string;
    name: string;
    mood?: Mood;
    relationships?: Record<string, Relationship>;
    activity?: Activity;
    plan?: Plan;
};

