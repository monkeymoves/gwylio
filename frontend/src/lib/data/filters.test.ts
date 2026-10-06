import { describe, expect, it } from 'vitest';
import { report, reports } from '../../../tests/fixtures';
import {
	activeFilterCount,
	filterReports,
	matchesReport,
	normaliseNeedle,
	parseQuery,
	serialiseQuery,
	withFilter,
	type ReportQuery
} from './filters';

// Two assessments that cut different ways on different requirements, so the
// "same assessment" rule for direction plus requirement can be seen.
const mixed = report({
	id: 'mixed',
	title: 'Drought declared in North Wales',
	summary: 'River  flows at a 190-year low.',
	state: 'tracking',
	bucket: 'brief',
	reliability: 'C',
	credibility: 3,
	lane: 'senedd',
	topics: ['water-resources'],
	hazards: ['drought-and-low-flows'],
	places: ['wales', 'north-wales'],
	last_changed: '2026-09-01',
	requirement_ids: ['si1', 'si4'],
	directions: ['threatens', 'informs_baseline'],
	assessments: [
		{ requirement_id: 'si1', code: 'SI1', set_id: 'nrw-corporate-plan', direction: 'threatens' },
		{ requirement_id: 'si4', code: 'SI4', set_id: 'other-set', direction: 'informs_baseline' }
	],
	set_ids: ['nrw-corporate-plan', 'other-set']
});

describe('matchesReport mirrors filter_reports', () => {
	const cases: Array<[string, ReportQuery, boolean]> = [
		['no filters', {}, true],
		['requirement held', { requirement: 'si4' }, true],
		['requirement not held', { requirement: 'si9' }, false],
		['direction on any assessment', { direction: 'threatens' }, true],
		['direction absent', { direction: 'supports' }, false],
		['direction and requirement on the same assessment', { requirement: 'si1', direction: 'threatens' }, true],
		['direction and requirement on different assessments', { requirement: 'si4', direction: 'threatens' }, false],
		['direction and set on the same assessment', { set: 'other-set', direction: 'informs_baseline' }, true],
		['direction and set on different assessments', { set: 'other-set', direction: 'threatens' }, false],
		['set held', { set: 'other-set' }, true],
		['set not held', { set: 'missing' }, false],
		['state exact', { state: 'tracking' }, true],
		['state other', { state: 'emerging' }, false],
		['bucket exact', { bucket: 'brief' }, true],
		['bucket other', { bucket: 'park' }, false],
		['lane exact', { lane: 'senedd' }, true],
		['lane other', { lane: 'welsh-government' }, false],
		['reliability letter', { reliability: 'C' }, true],
		['reliability other', { reliability: 'B' }, false],
		['credibility digit', { credibility: 3 }, true],
		['credibility other', { credibility: 2 }, false],
		['hazard tag', { hazard: 'drought-and-low-flows' }, true],
		['hazard missing', { hazard: 'avian-influenza' }, false],
		['topic tag', { topic: 'water-resources' }, true],
		['topic missing', { topic: 'peatland' }, false],
		['place tag', { place: 'north-wales' }, true],
		['place missing', { place: 'cardiff' }, false],
		['since on the day', { since: '2026-09-01' }, true],
		['since before', { since: '2026-08-01' }, true],
		['since after', { since: '2026-09-02' }, false],
		['q in the title, any case', { q: 'DROUGHT' }, true],
		['q in the summary, whitespace folded in the query', { q: '  190-year   low ' }, true],
		['q not whitespace folded in the text', { q: 'river flows' }, false],
		['q absent', { q: 'flooding' }, false],
		['q blank means any', { q: '   ' }, true],
		['two filters both pass', { state: 'tracking', lane: 'senedd' }, true],
		['two filters one fails', { state: 'tracking', lane: 'welsh-government' }, false]
	];

	it.each(cases)('%s', (_name, query, expected) => {
		expect(matchesReport(mixed, query)).toBe(expected);
	});

	it('keeps the order given', () => {
		const a = report({ id: 'a' });
		const b = report({ id: 'b', state: 'matured' });
		const c = report({ id: 'c' });
		expect(filterReports([a, b, c], { state: 'emerging' }).map((r) => r.id)).toEqual(['a', 'c']);
	});

	it('agrees with an independent count over the published snapshot', () => {
		const expected = reports.filter((r) =>
			r.assessments.some((a) => a.requirement_id === 'si4' && a.direction === 'threatens')
		).length;
		expect(filterReports(reports, { requirement: 'si4', direction: 'threatens' })).toHaveLength(
			expected
		);
		expect(filterReports(reports, {})).toHaveLength(reports.length);
	});
});

describe('normaliseNeedle', () => {
	it('lower-cases and folds whitespace', () => {
		expect(normaliseNeedle('  Net\tZero  TARGET ')).toBe('net zero target');
	});
});

describe('URL query round trip', () => {
	it('parses every key, with or without the question mark', () => {
		const query = parseQuery(
			'?set=nrw-corporate-plan&requirement=si4&direction=threatens&state=emerging&bucket=brief' +
				'&lane=senedd&hazard=drought-and-low-flows&topic=water-resources&place=wales' +
				'&reliability=B&credibility=2&since=2026-07-01&q=net+zero'
		);
		expect(query).toEqual({
			set: 'nrw-corporate-plan',
			requirement: 'si4',
			direction: 'threatens',
			state: 'emerging',
			bucket: 'brief',
			lane: 'senedd',
			hazard: 'drought-and-low-flows',
			topic: 'water-resources',
			place: 'wales',
			reliability: 'B',
			credibility: 2,
			since: '2026-07-01',
			q: 'net zero'
		});
	});

	it('drops empty values, unknown keys and values outside the vocabularies', () => {
		expect(
			parseQuery(
				'direction=sideways&state=&credibility=9&since=July&reliability=z&page=2&lane=%20%20'
			)
		).toEqual({});
	});

	it('accepts a lower-case reliability letter', () => {
		expect(parseQuery('reliability=c')).toEqual({ reliability: 'C' });
	});

	it('serialises in a fixed key order, leaving out what is unset', () => {
		expect(serialiseQuery({ direction: 'threatens', requirement: 'si4' })).toBe(
			'requirement=si4&direction=threatens'
		);
		expect(serialiseQuery({})).toBe('');
		expect(serialiseQuery({ q: '  ' })).toBe('');
	});

	const queries: ReportQuery[] = [
		{},
		{ requirement: 'si12' },
		{ requirement: 'si4', direction: 'threatens' },
		{ q: 'net zero & "nature"', credibility: 6, reliability: 'F' },
		{ set: 'nrw-corporate-plan', since: '2026-01-31', place: 'wales', topic: 'peatland' }
	];

	it.each(queries)('parse(serialise(q)) returns q: %o', (query) => {
		expect(parseQuery(serialiseQuery(query))).toEqual(query);
	});

	const strings = ['', 'requirement=si4&direction=threatens', 'state=matured&q=net+zero'];

	it.each(strings)('serialise(parse(s)) returns s: %s', (search) => {
		expect(serialiseQuery(parseQuery(search))).toBe(search);
	});
});

describe('withFilter and activeFilterCount', () => {
	it('sets, replaces and removes one key without touching the rest', () => {
		const start: ReportQuery = { requirement: 'si4' };
		const set = withFilter(start, 'direction', 'threatens');
		expect(set).toEqual({ requirement: 'si4', direction: 'threatens' });
		expect(start).toEqual({ requirement: 'si4' });
		expect(withFilter(set, 'direction', 'supports').direction).toBe('supports');
		expect(withFilter(set, 'direction', '')).toEqual({ requirement: 'si4' });
		expect(withFilter(set, 'credibility', '3').credibility).toBe(3);
	});

	it('keeps the search text as typed', () => {
		expect(withFilter({}, 'q', 'net ')).toEqual({ q: 'net ' });
	});

	it('counts the filters that are set', () => {
		expect(activeFilterCount({})).toBe(0);
		expect(activeFilterCount({ requirement: 'si4', direction: 'threatens' })).toBe(2);
	});
});
