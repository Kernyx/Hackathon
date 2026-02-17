/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AgentTraits } from './AgentTraits';
import type { PersonalityType } from './PersonalityType';
export type AiAgentDto = {
    userId?: string;
    username?: string;
    photoLink?: string;
    isMale?: boolean;
    age?: number;
    interests?: string;
    personalityType?: PersonalityType;
    traits?: AgentTraits;
    additionalInformation?: string;
};

