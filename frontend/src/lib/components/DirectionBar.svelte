<script lang="ts" module>
	import type { Direction, DirectionCounts } from '$lib/data/types.generated';

	export interface DirectionBarProps {
		counts: DirectionCounts;
		/** Labels by direction, from the enums; the raw value is the fallback. */
		labels?: Partial<Record<Direction, string>>;
		/** What the bar says when every count is zero. */
		emptyText?: string;
		/** Names what is counted, for screen readers, such as "Active reports on SI1". */
		caption?: string;
	}

	/** Bar order: the vocabulary order, which is also the legend order. */
	export const DIRECTION_ORDER: readonly Direction[] = [
		'supports',
		'threatens',
		'neutral',
		'informs_baseline'
	];

	export const DEFAULT_DIRECTION_LABELS: Record<Direction, string> = {
		supports: 'supports',
		threatens: 'threatens',
		neutral: 'two-way',
		informs_baseline: 'informs the baseline'
	};

	export interface DirectionSegment {
		direction: Direction;
		label: string;
		count: number;
		/** Share of the total, 0 to 1. */
		share: number;
	}

	/** The segments in bar order, zeros included, with their shares. Pure. */
	export function directionSegments(
		counts: DirectionCounts,
		labels: Partial<Record<Direction, string>> = {}
	): DirectionSegment[] {
		const total = DIRECTION_ORDER.reduce((sum, d) => sum + counts[d], 0);
		return DIRECTION_ORDER.map((direction) => ({
			direction,
			label: labels[direction] ?? DEFAULT_DIRECTION_LABELS[direction],
			count: counts[direction],
			share: total > 0 ? counts[direction] / total : 0
		}));
	}
</script>

<script lang="ts">
	let { counts, labels = {}, emptyText = 'No active reports', caption }: DirectionBarProps =
		$props();

	const segments = $derived(directionSegments(counts, labels));
	const total = $derived(segments.reduce((sum, s) => sum + s.count, 0));
	const summary = $derived(segments.map((s) => `${s.label} ${s.count}`).join(', '));
</script>

<div class="direction-bar" data-total={total}>
	{#if total > 0}
		<div class="bar" role="img" aria-label={caption ? `${caption}: ${summary}` : summary}>
			{#each segments as segment (segment.direction)}
				{#if segment.count > 0}
					<span
						class="segment"
						data-direction={segment.direction}
						style:flex-grow={segment.count}
						title="{segment.label}: {segment.count}"
					></span>
				{/if}
			{/each}
		</div>
	{:else}
		<div class="bar empty-track" aria-hidden="true"></div>
		<p class="empty">{emptyText}</p>
	{/if}
	<ul class="legend" aria-label="By direction">
		{#each segments as segment (segment.direction)}
			<li class:zero={segment.count === 0} data-direction={segment.direction}>
				<span class="swatch" aria-hidden="true"></span>
				<span class="label">{segment.label}</span>
				<span class="count">{segment.count}</span>
			</li>
		{/each}
	</ul>
</div>

<style>
	.direction-bar {
		display: grid;
		gap: var(--space-2);
		min-width: 0;
	}

	.bar {
		display: flex;
		gap: 2px;
		height: 12px;
		width: 100%;
	}

	.segment {
		flex-basis: 0;
		min-width: 4px;
		background: var(--seg);
	}

	.segment:first-child {
		border-top-left-radius: 4px;
		border-bottom-left-radius: 4px;
	}

	.segment:last-child {
		border-top-right-radius: 4px;
		border-bottom-right-radius: 4px;
	}

	.empty-track {
		border-radius: 4px;
		background: var(--bar-track);
	}

	.empty {
		margin: 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	[data-direction='supports'] {
		--seg: var(--dir-supports);
	}

	[data-direction='threatens'] {
		--seg: var(--dir-threatens);
	}

	[data-direction='neutral'] {
		--seg: var(--dir-neutral);
	}

	[data-direction='informs_baseline'] {
		--seg: var(--dir-informs-baseline);
	}

	.legend {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-3);
		margin: 0;
		padding: 0;
		list-style: none;
		font-size: var(--text-sm);
		color: var(--color-text);
	}

	.legend li {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		white-space: nowrap;
	}

	.legend li.zero {
		color: var(--color-text-muted);
	}

	.swatch {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		background: var(--seg);
	}

	.zero .swatch {
		opacity: 0.35;
	}

	.count {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}
</style>
