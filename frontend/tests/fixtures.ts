/**
 * Shared test data: a ReportSummary builder and the real published enums and
 * reports, read from the snapshot under static/data.
 */
import { readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import type { Enums, ReportSummary } from '$lib/data/types.generated';

const dataDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'static', 'data');

export function snapshot<T>(relative: string): T {
	return JSON.parse(readFileSync(path.join(dataDir, relative), 'utf8')) as T;
}

export const enums: Enums = snapshot<Enums>('enums.json');
export const reports: ReportSummary[] = snapshot<ReportSummary[]>('reports.json');

/** A minimal valid report summary; override what a test is about. */
export function report(overrides: Partial<ReportSummary> = {}): ReportSummary {
	return {
		id: 'a-report',
		title: 'A report',
		url: 'https://example.org/a',
		grading: 'B2',
		reliability: 'B',
		credibility: 2,
		report_type: 'policy',
		state: 'emerging',
		bucket: 'watch',
		directions: ['supports'],
		assessments: [
			{ requirement_id: 'si1', code: 'SI1', set_id: 'nrw-corporate-plan', direction: 'supports' }
		],
		requirement_ids: ['si1'],
		set_ids: ['nrw-corporate-plan'],
		lane: 'welsh-government',
		lane_name: 'Welsh Government',
		source_id: 'welsh-government',
		source_name: 'Welsh Government',
		topics: [],
		hazards: [],
		places: ['wales'],
		summary: 'A summary.',
		created_on: '2026-07-25',
		last_changed: '2026-07-25',
		last_verified: '2026-07-25',
		event_horizon: null,
		appearances: 0,
		distinct_sources: 0,
		flags: [],
		...overrides
	};
}
