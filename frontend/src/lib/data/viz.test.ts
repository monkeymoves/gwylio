import { describe, expect, it } from 'vitest';
import { seed } from '../../../tests/fixtures';
import type { FunnelCounts, RunDetail } from './types.generated';
import {
	HEAT_BINS,
	axisTicks,
	binLabel,
	formatRate,
	funnelStages,
	heatStep,
	niceMax
} from './viz';

describe('heat bins', () => {
	it.each([
		[0, 0],
		[-1, 0],
		[1, 1],
		[2, 2],
		[3, 3],
		[4, 3],
		[5, 4],
		[9, 4],
		[10, 5],
		[28, 5]
	])('count %i takes step %i', (count, step) => {
		expect(heatStep(count)).toBe(step);
	});

	it('reads thin for one and two, covered from three, matching the coverage rule', () => {
		expect(HEAT_BINS.filter((b) => b.status === 'thin').map((b) => b.step)).toEqual([1, 2]);
		expect(HEAT_BINS.filter((b) => b.status === 'covered').map((b) => b.min)).toEqual([3, 5, 10]);
	});

	it('labels each bin in words, with "to" for ranges', () => {
		expect(HEAT_BINS.map(binLabel)).toEqual(['1', '2', '3 to 4', '5 to 9', '10 or more']);
	});
});

describe('funnelStages', () => {
	const funnel: FunnelCounts = {
		raw: 30,
		dropped_own: 2,
		dropped_negative: 5,
		dropped_unrelated: 3,
		passed: 20,
		unique: 17,
		seen_before: 7,
		new: 0,
		reinforcements: 10
	};

	it('runs raw, passed, unique, new in that order with steps 1 to 4', () => {
		const stages = funnelStages(funnel);
		expect(stages.map((s) => s.key)).toEqual(['raw', 'passed', 'unique', 'new']);
		expect(stages.map((s) => s.count)).toEqual([30, 20, 17, 0]);
		expect(stages.map((s) => s.step)).toEqual([1, 2, 3, 4]);
	});

	it('names each drop and its counts', () => {
		const [raw, passed, unique, fresh] = funnelStages(funnel);
		expect(raw?.dropped).toBe(0);
		expect(passed?.reason).toBe('Dropped 10: own domain 2, negative term 5, unrelated 3.');
		expect(unique?.dropped).toBe(3);
		expect(unique?.reason).toContain('index echo');
		expect(fresh?.reason).toBe('Set aside 17: seen before 7, reinforcements of a report 10.');
	});

	it('gives shares of the raw hits, and zero shares when nothing came back', () => {
		expect(funnelStages(funnel).map((s) => s.share)).toEqual([1, 20 / 30, 17 / 30, 0]);
		const empty = funnelStages({ ...funnel, raw: 0, passed: 0, unique: 0, new: 0, seen_before: 0, reinforcements: 0, dropped_own: 0, dropped_negative: 0, dropped_unrelated: 0 });
		expect(empty.every((s) => s.share === 0)).toBe(true);
	});

	it('balances on every seed run: each stage loses exactly what its reason names', () => {
		const run = seed<RunDetail>('run_first.json');
		const [raw, passed, unique, fresh] = funnelStages(run.funnel);
		const f = run.funnel;
		expect((raw?.count ?? 0) - (passed?.count ?? 0)).toBe(
			f.dropped_own + f.dropped_negative + f.dropped_unrelated
		);
		expect((unique?.count ?? 0) - (fresh?.count ?? 0)).toBe(f.seen_before + f.reinforcements);
	});
});

describe('axis helpers', () => {
	it.each([
		[0, 1],
		[1, 1],
		[3, 5],
		[13, 20],
		[30, 50],
		[100, 100],
		[101, 200]
	])('niceMax(%i) is %i', (value, max) => {
		expect(niceMax(value)).toBe(max);
	});

	it('ticks from zero through half to the nice maximum', () => {
		expect(axisTicks(30)).toEqual([0, 25, 50]);
		expect(axisTicks(1)).toEqual([0, 1]);
		expect(axisTicks(0)).toEqual([0, 1]);
	});

	it('formats rates as whole percentages, with a fallback for none', () => {
		expect(formatRate(0.5882)).toBe('59%');
		expect(formatRate(0)).toBe('0%');
		expect(formatRate(null)).toBe('none');
		expect(formatRate(undefined, 'n/a')).toBe('n/a');
	});
});
