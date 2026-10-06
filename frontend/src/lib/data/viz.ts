/**
 * Pure helpers for the charts and heatmaps: the heatmap's count bins, the
 * funnel stages with their drop reasons, and axis ticks. Colours live in
 * `tokens.css` (`--seq-N`, `--funnel-N`, `--viz-series-1`); these functions only
 * decide which step a value takes and what its label says.
 */
import type { CoverageStatus, FunnelCounts } from './types.generated';

/** One step of the heatmap's sequential scale: the counts it covers. */
export interface HeatBin {
	/** 1 to 5: the `--seq-N` step. */
	step: number;
	min: number;
	/** Null for the open-ended top bin. */
	max: number | null;
	/** The coverage status every count in the bin reads as. */
	status: CoverageStatus;
}

/**
 * The bins, fixed so the same count always takes the same shade on every
 * table. One and two active reports read thin; three or more read covered.
 */
export const HEAT_BINS: readonly HeatBin[] = [
	{ step: 1, min: 1, max: 1, status: 'thin' },
	{ step: 2, min: 2, max: 2, status: 'thin' },
	{ step: 3, min: 3, max: 4, status: 'covered' },
	{ step: 4, min: 5, max: 9, status: 'covered' },
	{ step: 5, min: 10, max: null, status: 'covered' }
];

/** The `--seq-N` step for a count: 0 for no reports (no shade), else 1 to 5. */
export function heatStep(count: number): number {
	if (count <= 0) return 0;
	const bin = HEAT_BINS.find((b) => count >= b.min && (b.max === null || count <= b.max));
	return bin?.step ?? HEAT_BINS.length;
}

/** A bin's counts as words: "1", "3 to 4", "10 or more". */
export function binLabel(bin: HeatBin): string {
	if (bin.max === null) return `${bin.min} or more`;
	return bin.min === bin.max ? String(bin.min) : `${bin.min} to ${bin.max}`;
}

/** One bar of the funnel diagram. */
export interface FunnelStage {
	key: 'raw' | 'passed' | 'unique' | 'new';
	label: string;
	count: number;
	/** 1 to 4: the `--funnel-N` step. */
	step: number;
	/** Share of the raw hits, 0 to 1. */
	share: number;
	/** How many the stage removed from the one before; 0 for raw. */
	dropped: number;
	/** Why they went, with the counts. */
	reason: string;
}

/**
 * The funnel from raw hits down to new candidates, each stage with what it
 * dropped and why. Pure.
 */
export function funnelStages(f: FunnelCounts): FunnelStage[] {
	const share = (n: number) => (f.raw > 0 ? n / f.raw : 0);
	const gated = f.raw - f.passed;
	const merged = f.passed - f.unique;
	const known = f.unique - f.new;
	return [
		{
			key: 'raw',
			label: 'Raw hits',
			count: f.raw,
			step: 1,
			share: share(f.raw),
			dropped: 0,
			reason: 'Every hit the collectors returned.'
		},
		{
			key: 'passed',
			label: 'Passed the gates',
			count: f.passed,
			step: 2,
			share: share(f.passed),
			dropped: gated,
			reason: `Dropped ${gated}: own domain ${f.dropped_own}, negative term ${f.dropped_negative}, unrelated ${f.dropped_unrelated}.`
		},
		{
			key: 'unique',
			label: 'Unique candidates',
			count: f.unique,
			step: 3,
			share: share(f.unique),
			dropped: merged,
			reason: `Merged ${merged}: the same canonical address found more than once in the run (index echo).`
		},
		{
			key: 'new',
			label: 'New candidates',
			count: f.new,
			step: 4,
			share: share(f.new),
			dropped: known,
			reason: `Set aside ${known}: seen before ${f.seen_before}, reinforcements of a report ${f.reinforcements}.`
		}
	];
}

/** The smallest 1, 2 or 5 times a power of ten at or above the value; 1 for zero. */
export function niceMax(value: number): number {
	if (value <= 1) return 1;
	const power = 10 ** Math.floor(Math.log10(value));
	for (const factor of [1, 2, 5, 10]) {
		if (factor * power >= value) return factor * power;
	}
	return 10 * power;
}

/** Axis ticks from zero to the nice maximum: 0, half, max (whole numbers only). */
export function axisTicks(max: number): number[] {
	const top = niceMax(max);
	const half = top / 2;
	return Number.isInteger(half) && half > 0 ? [0, half, top] : [0, top];
}

/** A rate from 0 to 1 as a whole percentage, or the fallback when there is none. */
export function formatRate(rate: number | null | undefined, fallback = 'none'): string {
	if (rate === null || rate === undefined || Number.isNaN(rate)) return fallback;
	return `${Math.round(rate * 100)}%`;
}
