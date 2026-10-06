import { describe, expect, it } from 'vitest';
import { seed, snapshot } from '../../../tests/fixtures';
import { sortRows, type Column } from '$lib/components/DataTable.svelte';
import {
	SOURCE_SORT,
	filterSources,
	laneOptions,
	parseSourceQuery,
	serialiseSourceQuery,
	silentSources,
	type SourceColumnKey
} from './sources';
import type { SourceSummary, SourcesHealth } from './types.generated';

const seedSources = seed<SourceSummary[]>('sources.json');
const seedHealth = seed<SourcesHealth>('sources_health.json');
const realSources = snapshot<SourceSummary[]>('sources.json');

function columnsFor(key: SourceColumnKey): Column<SourceSummary>[] {
	return [{ key, label: key, sortValue: SOURCE_SORT[key] }];
}

function sortedIds(key: SourceColumnKey, direction: 'ascending' | 'descending'): string[] {
	return sortRows(seedSources, columnsFor(key), { key, direction }).map((s) => s.id);
}

describe('source query', () => {
	it.each([
		['', {}],
		['?lane=senedd', { lane: 'senedd' }],
		['lane=%20senedd%20', { lane: 'senedd' }],
		['lane=&other=1', {}]
	])('parses %j', (input, expected) => {
		expect(parseSourceQuery(input)).toEqual(expected);
	});

	it('round trips through the query string', () => {
		for (const query of [{}, { lane: 'welsh-government' }]) {
			expect(parseSourceQuery(serialiseSourceQuery(query))).toEqual(query);
		}
		expect(serialiseSourceQuery({})).toBe('');
		expect(serialiseSourceQuery({ lane: 'senedd' })).toBe('lane=senedd');
	});
});

describe('filterSources', () => {
	it('keeps every source with no filter, and only the lane asked for with one', () => {
		expect(filterSources(realSources, {})).toHaveLength(realSources.length);
		const senedd = filterSources(realSources, { lane: 'senedd' });
		expect(senedd.length).toBe(realSources.filter((s) => s.lane === 'senedd').length);
		expect(senedd.length).toBeGreaterThan(0);
		expect(senedd.every((s) => s.lane === 'senedd')).toBe(true);
	});

	it('returns nothing for a lane no source sits in', () => {
		expect(filterSources(realSources, { lane: 'no-such-lane' })).toEqual([]);
	});
});

describe('laneOptions', () => {
	it('lists each lane once, by name, with its source count', () => {
		const options = laneOptions(realSources);
		const lanes = new Set(realSources.map((s) => s.lane));
		expect(options.map((o) => o.value).sort()).toEqual([...lanes].sort());
		const labels = options.map((o) => o.label);
		expect(labels).toEqual([...labels].sort((a, b) => a.localeCompare(b, 'en-GB')));
		const total = options.reduce((sum, o) => sum + Number(/\((\d+)\)$/.exec(o.label)?.[1]), 0);
		expect(total).toBe(realSources.length);
	});
});

describe('SOURCE_SORT', () => {
	it('sorts reliability A first and F last', () => {
		const letters = sortRows(seedSources, columnsFor('reliability'), {
			key: 'reliability',
			direction: 'ascending'
		}).map((s) => s.reliability);
		expect(letters).toEqual([...letters].sort());
	});

	it('puts sources with no promotion rate last in both directions', () => {
		const withRate = seedSources.filter((s) => s.promotion_rate !== null).length;
		for (const direction of ['ascending', 'descending'] as const) {
			const ids = sortedIds('promotion_rate', direction);
			const rates = ids.map((id) => seedSources.find((s) => s.id === id)?.promotion_rate);
			expect(rates.slice(withRate).every((r) => r === null)).toBe(true);
			expect(rates.slice(0, withRate).every((r) => r !== null)).toBe(true);
		}
	});

	it('sorts readings most productive first', () => {
		const readings = sortRows(seedSources, columnsFor('reading'), {
			key: 'reading',
			direction: 'ascending'
		}).map((s) => s.reading);
		expect(readings[0]).toBe('earning_its_place');
		expect(readings[readings.length - 1]).toBe('silent');
	});

	it('sorts raw hits as numbers, not text', () => {
		const hits = sortRows(seedSources, columnsFor('raw_hits'), {
			key: 'raw_hits',
			direction: 'descending'
		}).map((s) => s.raw_hits);
		expect(hits).toEqual([...hits].sort((a, b) => b - a));
	});

	it('has a sort value for every column', () => {
		const source = seedSources[0];
		if (!source) throw new Error('no seed source');
		for (const key of Object.keys(SOURCE_SORT) as SourceColumnKey[]) {
			expect(SOURCE_SORT[key](source)).not.toBeUndefined();
		}
	});
});

describe('silentSources', () => {
	it('names every silent source with its lane, in the health model order', () => {
		const silent = silentSources(seedHealth, seedSources);
		expect(silent.map((s) => s.id)).toEqual(seedHealth.silent_sources);
		expect(silent.every((s) => s.lane_name !== null)).toBe(true);
		expect(silent[0]?.name).toBe(seedSources.find((s) => s.id === silent[0]?.id)?.name);
	});

	it('keeps an id the watchlist does not know, as a bare id', () => {
		const silent = silentSources({ ...seedHealth, silent_sources: ['gone'] }, seedSources);
		expect(silent).toEqual([{ id: 'gone', name: 'gone', lane_name: null }]);
	});
});
