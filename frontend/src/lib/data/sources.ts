/**
 * The watchlist page's filter, sort values and silent-source list. All pure,
 * so the page only wires them to the URL and the table.
 *
 * The lane filter lives in the URL query string (`?lane=<id>`) like the report
 * filters: the prerendered page lists every source, and once hydrated the
 * filter comes from the address and every change is written back to it.
 */
import type { FilterOption } from '$lib/components/FilterBar.svelte';
import type {
	Reliability,
	SourceStatus,
	SourceSummary,
	SourcesHealth,
	YieldReading
} from './types.generated';

/** The filters on the watchlist. A missing key means "any". */
export interface SourceQuery {
	lane?: string;
}

/** Read the query from a query string or URLSearchParams; blanks are dropped. */
export function parseSourceQuery(input: string | URLSearchParams): SourceQuery {
	const params = typeof input === 'string' ? new URLSearchParams(input) : input;
	const lane = params.get('lane')?.trim();
	return lane ? { lane } : {};
}

/** Write the query as a query string with no leading `?`; empty when no filter is set. */
export function serialiseSourceQuery(query: SourceQuery): string {
	const params = new URLSearchParams();
	if (query.lane?.trim()) params.set('lane', query.lane.trim());
	return params.toString();
}

/** The sources that pass the query, in the order given. */
export function filterSources(
	sources: readonly SourceSummary[],
	query: SourceQuery
): SourceSummary[] {
	return sources.filter((source) => query.lane === undefined || source.lane === query.lane);
}

/** One choice per lane some source sits in, by lane name, with how many sources it holds. */
export function laneOptions(sources: readonly SourceSummary[]): FilterOption[] {
	const lanes = new Map<string, { name: string; count: number }>();
	for (const source of sources) {
		const entry = lanes.get(source.lane) ?? { name: source.lane_name, count: 0 };
		entry.count += 1;
		lanes.set(source.lane, entry);
	}
	return [...lanes]
		.sort(([, a], [, b]) => a.name.localeCompare(b.name, 'en-GB'))
		.map(([value, { name, count }]) => ({ value, label: `${name} (${count})` }));
}

const RELIABILITY_ORDER: readonly Reliability[] = ['A', 'B', 'C', 'D', 'E', 'F'];
const STATUS_ORDER: readonly SourceStatus[] = ['active', 'parked', 'retired'];

/** Readings from most to least productive. */
export const READING_ORDER: readonly YieldReading[] = [
	'earning_its_place',
	'low_volume',
	'high_volume_no_promotions',
	'silent'
];

/** The column keys of the watchlist table, in display order. */
export type SourceColumnKey =
	| 'name'
	| 'lane'
	| 'discipline'
	| 'reliability'
	| 'status'
	| 'trusted'
	| 'raw_hits'
	| 'unique_candidates'
	| 'promoted'
	| 'promotion_rate'
	| 'last_productive_run'
	| 'reading';

/**
 * The value each column sorts by. Closed vocabularies sort in their own
 * order (reliability A first, readings most productive first); a source with
 * no promotion rate or no productive run sorts last either way (DataTable
 * puts nulls last).
 */
export const SOURCE_SORT: Record<SourceColumnKey, (s: SourceSummary) => string | number | null> = {
	name: (s) => s.name,
	lane: (s) => s.lane_name,
	discipline: (s) => s.discipline,
	reliability: (s) => RELIABILITY_ORDER.indexOf(s.reliability),
	status: (s) => STATUS_ORDER.indexOf(s.status),
	trusted: (s) => (s.trusted ? 0 : 1),
	raw_hits: (s) => s.raw_hits,
	unique_candidates: (s) => s.unique_candidates,
	promoted: (s) => s.promoted,
	promotion_rate: (s) => s.promotion_rate,
	last_productive_run: (s) => s.last_productive_run,
	reading: (s) => READING_ORDER.indexOf(s.reading)
};

/**
 * The silent sources named by the health read model, as full watchlist
 * entries in the health model's order. An id the watchlist does not know is
 * kept as a bare id so nothing silently disappears.
 */
export function silentSources(
	health: SourcesHealth,
	sources: readonly SourceSummary[]
): { id: string; name: string; lane_name: string | null }[] {
	const byId = new Map(sources.map((s) => [s.id, s]));
	return health.silent_sources.map((id) => {
		const source = byId.get(id);
		return { id, name: source?.name ?? id, lane_name: source?.lane_name ?? null };
	});
}
