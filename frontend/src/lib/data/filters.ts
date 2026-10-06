/**
 * The report list filters: the query shape, the client-side filter and the
 * URL query string round trip. All pure functions.
 *
 * The semantics mirror `filter_reports` in
 * `backend/src/gwylio/infrastructure/readmodels.py`, so the static site and
 * `GET /api/v1/reports` agree: ids and enums match exactly; `direction`
 * narrows to reports with an assessment in that direction, and when
 * `requirement` or `set` is also given that same assessment must be on the
 * requirement or in the set; `since` keeps reports whose `last_changed` is on
 * or after it; `q` matches the title or summary, ignoring case, with runs of
 * whitespace in the query folded to one space.
 */
import type {
	Bucket,
	Credibility,
	Direction,
	IndicatorState,
	Reliability,
	ReportSummary
} from './types.generated';

/** The filters on the report list. A missing key means "any". */
export interface ReportQuery {
	set?: string;
	requirement?: string;
	direction?: Direction;
	state?: IndicatorState;
	bucket?: Bucket;
	lane?: string;
	hazard?: string;
	topic?: string;
	place?: string;
	reliability?: Reliability;
	credibility?: Credibility;
	since?: string;
	q?: string;
}

export type FilterKey = keyof ReportQuery;

/** Every filter key, in the order the query string writes them. Names match the API. */
export const FILTER_KEYS: readonly FilterKey[] = [
	'set',
	'requirement',
	'direction',
	'state',
	'bucket',
	'lane',
	'hazard',
	'topic',
	'place',
	'reliability',
	'credibility',
	'since',
	'q'
];

export const DIRECTIONS: readonly Direction[] = [
	'supports',
	'threatens',
	'neutral',
	'informs_baseline'
];
export const STATES: readonly IndicatorState[] = [
	'emerging',
	'tracking',
	'reinforced',
	'matured',
	'faded',
	'parked'
];
export const BUCKETS: readonly Bucket[] = ['brief', 'follow_up', 'watch', 'park'];
export const RELIABILITIES: readonly Reliability[] = ['A', 'B', 'C', 'D', 'E', 'F'];
export const CREDIBILITIES: readonly Credibility[] = [1, 2, 3, 4, 5, 6];

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

function oneOf<T extends string>(allowed: readonly T[], value: string): T | undefined {
	return (allowed as readonly string[]).includes(value) ? (value as T) : undefined;
}

/** The search text as the filter compares it: lower case, whitespace folded. */
export function normaliseNeedle(q: string): string {
	return q.toLowerCase().split(/\s+/).filter(Boolean).join(' ');
}

/** True when the report passes every filter in the query. */
export function matchesReport(report: ReportSummary, query: ReportQuery): boolean {
	const { set, requirement, direction } = query;
	if (set !== undefined && !report.set_ids.includes(set)) return false;
	if (requirement !== undefined && !report.requirement_ids.includes(requirement)) return false;
	if (
		direction !== undefined &&
		!report.assessments.some(
			(a) =>
				a.direction === direction &&
				(requirement === undefined || a.requirement_id === requirement) &&
				(set === undefined || a.set_id === set)
		)
	) {
		return false;
	}
	if (query.state !== undefined && report.state !== query.state) return false;
	if (query.bucket !== undefined && report.bucket !== query.bucket) return false;
	if (query.lane !== undefined && report.lane !== query.lane) return false;
	if (query.reliability !== undefined && report.reliability !== query.reliability) return false;
	if (query.credibility !== undefined && report.credibility !== query.credibility) return false;
	if (query.hazard !== undefined && !report.hazards.includes(query.hazard)) return false;
	if (query.place !== undefined && !report.places.includes(query.place)) return false;
	if (query.topic !== undefined && !report.topics.includes(query.topic)) return false;
	if (query.since !== undefined && report.last_changed < query.since) return false;
	if (query.q !== undefined) {
		const needle = normaliseNeedle(query.q);
		if (
			needle &&
			!report.title.toLowerCase().includes(needle) &&
			!report.summary.toLowerCase().includes(needle)
		) {
			return false;
		}
	}
	return true;
}

/** The reports that pass every filter, in the order given. */
export function filterReports(reports: readonly ReportSummary[], query: ReportQuery): ReportSummary[] {
	return reports.filter((report) => matchesReport(report, query));
}

/**
 * Read a query from a URL query string (with or without the leading `?`) or
 * URLSearchParams. Empty values, unknown keys and values outside a closed
 * vocabulary are dropped, so a hand-edited URL never breaks the page.
 */
export function parseQuery(input: string | URLSearchParams): ReportQuery {
	const params = typeof input === 'string' ? new URLSearchParams(input) : input;
	const query: ReportQuery = {};
	for (const key of FILTER_KEYS) {
		const raw = params.get(key);
		if (raw === null) continue;
		const value = key === 'q' ? raw : raw.trim();
		if (!value.trim()) continue;
		setKey(query, key, value);
	}
	return query;
}

function setKey(query: ReportQuery, key: FilterKey, value: string): void {
	switch (key) {
		case 'direction':
			query.direction = oneOf(DIRECTIONS, value);
			break;
		case 'state':
			query.state = oneOf(STATES, value);
			break;
		case 'bucket':
			query.bucket = oneOf(BUCKETS, value);
			break;
		case 'reliability':
			query.reliability = oneOf(RELIABILITIES, value.toUpperCase());
			break;
		case 'credibility': {
			const digit = Number(value);
			query.credibility = (CREDIBILITIES as readonly number[]).includes(digit)
				? (digit as Credibility)
				: undefined;
			break;
		}
		case 'since':
			query.since = ISO_DATE.test(value) ? value : undefined;
			break;
		default:
			query[key] = value;
	}
	if (query[key] === undefined) delete query[key];
}

/**
 * Write a query as a URL query string with no leading `?`, keys in
 * `FILTER_KEYS` order and empty values left out, so equal queries always
 * serialise to equal strings.
 */
export function serialiseQuery(query: ReportQuery): string {
	const params = new URLSearchParams();
	for (const key of FILTER_KEYS) {
		const value = query[key];
		if (value === undefined) continue;
		const text = String(value);
		if (!text.trim()) continue;
		params.set(key, text);
	}
	return params.toString();
}

/** A copy of the query with one filter set, or removed when the value is empty. */
export function withFilter(query: ReportQuery, key: FilterKey, value: string): ReportQuery {
	const next: ReportQuery = { ...query };
	delete next[key];
	if (value.trim()) setKey(next, key, value);
	return next;
}

/** How many filters are set. */
export function activeFilterCount(query: ReportQuery): number {
	return FILTER_KEYS.filter((key) => query[key] !== undefined).length;
}
