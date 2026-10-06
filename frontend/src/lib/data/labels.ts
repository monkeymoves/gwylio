/**
 * Labels and formatting for values from the snapshot. Wording for closed
 * vocabularies comes from `enums.json` (the `Enums` read model), so the site
 * and the products say the same thing; these helpers only look it up.
 */
import type { EnumValue, Enums } from './types.generated';

/** The enum vocabularies that are lists of values (not the standing sentences). */
export type EnumName = {
	[K in keyof Enums]: Enums[K] extends EnumValue[] ? K : never;
}[keyof Enums];

/** The value's label from the vocabulary, or the value with underscores as spaces. */
export function enumLabel(enums: Enums | undefined, name: EnumName, value: string | number): string {
	const text = String(value);
	const found = enums?.[name].find((entry) => entry.value === text);
	return found?.label ?? text.replaceAll('_', ' ');
}

/** The value's meaning sentence, when the vocabulary carries one. */
export function enumMeaning(
	enums: Enums | undefined,
	name: EnumName,
	value: string | number
): string | null {
	const text = String(value);
	return enums?.[name].find((entry) => entry.value === text)?.meaning ?? null;
}

/** Capitalise the first letter, for a label that opens a line. */
export function capitalise(text: string): string {
	return text ? text.charAt(0).toUpperCase() + text.slice(1) : text;
}

/** A readable name from a kebab-case id, for when no catalogue name is known. */
export function humaniseId(id: string): string {
	return capitalise(id.replaceAll('-', ' ').replaceAll('_', ' '));
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** 2026-07-25 as 25 Jul 2026; null or malformed input as the fallback. */
export function formatDate(iso: string | null | undefined, fallback = 'none'): string {
	if (!iso) return fallback;
	const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
	if (!match) return iso;
	const [, year, month, day] = match;
	const name = MONTHS[Number(month) - 1];
	return name ? `${Number(day)} ${name} ${year}` : iso;
}

/** 2026-10-06T10:19:08Z as 6 Oct 2026, 10:19 UTC. */
export function formatInstant(iso: string | null | undefined, fallback = 'none'): string {
	if (!iso) return fallback;
	const match = /^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})/.exec(iso);
	if (!match) return iso;
	return `${formatDate(match[1])}, ${match[2]}:${match[3]} UTC`;
}

/** "1 report", "3 reports". */
export function plural(count: number, one: string, many = `${one}s`): string {
	return `${count} ${count === 1 ? one : many}`;
}

/** Every label of one vocabulary by value, such as { neutral: 'two-way', ... }. */
export function labelMap(enums: Enums | undefined, name: EnumName): Record<string, string> {
	return Object.fromEntries((enums?.[name] ?? []).map((entry) => [entry.value, entry.label]));
}
