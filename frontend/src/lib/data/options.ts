/**
 * The choices each report filter offers, built from the snapshot. Pure.
 *
 * Closed vocabularies list every value with its label from the enums.
 * Requirements come from the requirement sets, in set order. Lanes, topics,
 * hazards and places list only the values some report carries, so no choice
 * leads to an empty list by construction.
 */
import type { FilterOption, FilterOptions } from '$lib/components/FilterBar.svelte';
import type { EnumName } from './labels';
import { humaniseId } from './labels';
import type { Enums, ReportSummary, RequirementSetDetail } from './types.generated';

export interface TagNameMaps {
	topics: Record<string, string>;
	hazards: Record<string, string>;
	places: Record<string, string>;
}

function fromEnum(enums: Enums, name: EnumName, withValue = false): FilterOption[] {
	return enums[name].map((entry) => ({
		value: entry.value,
		label: withValue ? `${entry.value}: ${entry.label}` : entry.label
	}));
}

function byLabel(a: FilterOption, b: FilterOption): number {
	return a.label.localeCompare(b.label, 'en-GB');
}

function usedTags(
	reports: readonly ReportSummary[],
	pick: (report: ReportSummary) => string[],
	names: Record<string, string>
): FilterOption[] {
	const ids = new Set(reports.flatMap(pick));
	return [...ids].map((id) => ({ value: id, label: names[id] ?? humaniseId(id) })).sort(byLabel);
}

export function buildFilterOptions(
	reports: readonly ReportSummary[],
	enums: Enums,
	sets: readonly RequirementSetDetail[],
	tagNames: TagNameMaps
): FilterOptions {
	const lanes = new Map<string, string>();
	for (const report of reports) lanes.set(report.lane, report.lane_name);
	return {
		requirement: sets.flatMap((set) =>
			set.requirements.map((r) => ({ value: r.id, label: `${r.code} ${r.short}` }))
		),
		direction: fromEnum(enums, 'direction'),
		state: fromEnum(enums, 'indicator_state'),
		bucket: fromEnum(enums, 'bucket'),
		lane: [...lanes].map(([value, label]) => ({ value, label })).sort(byLabel),
		hazard: usedTags(reports, (r) => r.hazards, tagNames.hazards),
		topic: usedTags(reports, (r) => r.topics, tagNames.topics),
		place: usedTags(reports, (r) => r.places, tagNames.places),
		reliability: fromEnum(enums, 'reliability', true),
		credibility: fromEnum(enums, 'credibility', true)
	};
}
