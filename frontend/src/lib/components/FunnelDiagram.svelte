<script lang="ts" module>
	import type { FunnelCounts } from '$lib/data/types.generated';

	export interface FunnelDiagramProps {
		funnel: FunnelCounts;
		/** Names the diagram for screen readers. */
		caption?: string;
	}
</script>

<script lang="ts">
	import { formatRate, funnelStages } from '$lib/data/viz';

	let { funnel, caption = 'Scan funnel, from raw hits to new candidates' }: FunnelDiagramProps =
		$props();

	const stages = $derived(funnelStages(funnel));
</script>

<ol class="funnel" aria-label={caption}>
	{#each stages as stage (stage.key)}
		<li class="stage" data-stage={stage.key}>
			<div class="head">
				<span class="label">{stage.label}</span>
				<span class="count">{stage.count}</span>
				{#if stage.key !== 'raw'}
					<span class="share">{formatRate(stage.share, '0%')} of raw hits</span>
				{/if}
			</div>
			<div class="track">
				{#if stage.count > 0}
					<span
						class="bar"
						style:width="{Math.max(stage.share * 100, 0.5)}%"
						style:--bar={`var(--funnel-${stage.step})`}
						title="{stage.label}: {stage.count}"
					></span>
				{/if}
			</div>
			<p class="reason">{stage.reason}</p>
		</li>
	{/each}
</ol>

<style>
	.funnel {
		display: grid;
		gap: var(--space-3);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.stage {
		display: grid;
		gap: var(--space-1);
	}

	.head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: 0 var(--space-2);
	}

	.label {
		font-weight: 600;
	}

	.count {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.share {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	/* The baseline is a hairline on the left; every bar grows from it. */
	.track {
		height: 18px;
		border-left: 1px solid var(--viz-axis);
	}

	.bar {
		display: block;
		height: 100%;
		border-radius: 0 4px 4px 0;
		background: var(--bar);
	}

	.reason {
		margin: 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}
</style>
