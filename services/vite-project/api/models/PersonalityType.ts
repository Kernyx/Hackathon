/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Тип личности агента
 */
export const PersonalityType = {
    ALTRUIST: 'Альтруист (добрый)',
    MACHIAVELLIAN: 'Макиавеллист (злой)',
    REBEL: 'Бунтарь (непредсказуемый)',
    STOIC: 'Стоик (хладнокровный)',
    INDIVIDUAL: 'Индивидуальный (пользовательский)',
} as const;

export type PersonalityType = typeof PersonalityType[keyof typeof PersonalityType];
