<script lang="ts" module>
	import type { FunnelPoint } from '$lib/data/types.generated';

	export interface FunnelTrendProps {
		/** Runs oldest first, as the health read model lists them. */
		trend: FunnelPoint[];
	}

	/** The four measures the trend shows, one small chart each, on one shared scale. */
	export const TREND_MEASURES = [
		{ key: 'raw', label: 'Raw hits' },
		{ key: 'unique', label: 'Unique candidates' },
		{ key: 'new', label: 'New candidates' },
		{ key: 'reinforcements', label: 'Reinforcements' }
	] as const;

	export type TrendMeasure = (typeof TREND_MEASURES)[number]['key'];

	/** One measure's value for a run. */
	export function measureOf(point: FunnelPoint, key: TrendMeasure): number {
		return point.funnel[key];
	}
</script>

<script lang="ts">
	import { formatDate, formatInstant } from '$lib/data/labels';
	import { axisTicks } from '$lib/data/viz';

	let { trend }: FunnelTrendProps = $props();

	// One scale for every panel, so the four charts compare at a glance.
	const largest = $derived(
		Math.max(0, ...trend.flatMap((p) => TREND_MEASURES.map((m) => measureOf(p, m.key))))
	);
	const ticks = $derived(axisTicks(largest));
	const top = $derived(ticks[ticks.length - 1] ?? 1);
	const first = $derived(trend[0]);
	const last = $derived(trend[trend.length - 1]);
</script>

<figure class="trend">
	<div class="panels">
		{#each TREND_MEASURES as measure (measure.key)}
			<section class="panel" data-measure={measure.key} aria-label="{measure.label} per run">
				<h3>{measure.label}</h3>
				<div class="plot">
					<div class="y-axis" aria-hidden="true">
						{#each ticks as tick (tick)}
							<span class="tick" style:bottom="{(tick / top) * 100}%">{tick}</span>
						{/each}
					</div>
					<div class="area">
						{#each ticks as tick (tick)}
							<span class="grid" style:bottom="{(tick / top) * 100}%" aria-hidden="true"></span>
						{/each}
						<ol class="columns">
							{#each trend as point, i (point.run_id)}
								{@const value = measureOf(point, measure.key)}
								<li
									class="column"
									title="{formatInstant(point.started_at)}, run {point.run_id}: {value}"
								>
									<span class="visually-hidden"
										>{formatDate(point.started_at)}: {value}</span
									>
									{#if value > 0}
										<span class="bar" style:height="{(value / top) * 100}%"></span>
									{/if}
									{#if i === trend.length - 1}
										<span class="end-label" style:bottom="{(value / top) * 100}%">{value}</span>
									{/if}
								</li>
							{/each}
						</ol>
					</div>
				</div>
				<div class="x-axis" aria-hidden="true">
					<span>{formatDate(first?.started_at)}</span>
					{#if trend.length > 1}<span>{formatDate(last?.started_at)}</span>{/if}
				</div>
			</section>
		{/each}
	</div>
	<figcaption>
		<span>Vertical axis: count per run, one scale for all four charts. Horizontal axis: scan runs by start date, oldest on the left; the latest run's value is labelled.</span>
		<span class="source">Source: gwylio scan runs</span>
	</figcaption>
</figure>

<style>
	.trend {
		display: grid;
		gap: var(--space-3);
		margin: 0;
	}

	.panels {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
		gap: var(--space-4);
	}

	.panel {
		min-width: 0;
	}

	h3 {
		margin: 0 0 var(--space-4);
		font-size: var(--text-sm);
	}

	.plot {
		display: grid;
		grid-template-columns: 2rem minmax(0, 1fr);
		height: 120px;
	}

	.y-axis {
		position: relative;
		font-size: 0.75rem;
		color: var(--color-text-muted);
		font-variant-numeric: tabular-nums;
	}

	.tick {
		position: absolute;
		right: var(--space-1);
		transform: translateY(50%);
		line-height: 1;
	}

	.area {
		position: relative;
		border-bottom: 1px solid var(--viz-axis);
	}

	.grid {
		position: absolute;
		left: 0;
		right: 0;
		border-top: 1px solid var(--viz-grid);
	}

	.columns {
		position: absolute;
		inset: 0;
		display: flex;
		align-items: flex-end;
		gap: 2px;
		margin: 0;
		padding: 0 var(--space-1);
		list-style: none;
	}

	.column {
		position: relative;
		display: flex;
		flex: 1 1 0;
		align-items: flex-end;
		justify-content: center;
		height: 100%;
	}

	.column:hover .bar {
		filter: brightness(1.15);
	}

	.bar {
		display: block;
		width: 100%;
		max-width: 24px;
		border-radius: 4px 4px 0 0;
		background: var(--viz-series-1);
	}

	.end-label {
		position: absolute;
		left: 50%;
		transform: translate(-50%, -2px);
		font-size: 0.75rem;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
		color: var(--color-text);
		line-height: 1;
		margin-bottom: 2px;
	}

	.x-axis {
		display: flex;
		justify-content: space-between;
		margin-left: 2rem;
		padding-top: var(--space-1);
		font-size: 0.75rem;
		color: var(--color-text-muted);
	}

	figcaption {
		display: grid;
		gap: var(--space-1);
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	.source {
		font-style: italic;
	}
</style>
