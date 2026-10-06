<script lang="ts">
	import CredibilityBars from '$lib/components/CredibilityBars.svelte';
	import Heatmap from '$lib/components/Heatmap.svelte';
	import PageHead from '$lib/components/PageHead.svelte';
	import { COVERAGE_NOTES } from '$lib/content/about';
	import { plural } from '$lib/data/labels';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const coverage = $derived(data.coverage);
	const lanes = $derived(coverage.lanes);
</script>

<PageHead title="Coverage: {coverage.set_name}" eyebrow="Evaluation">
	<p>
		The coverage audit runs down both axes: the requirements, by the lane each active report was
		found in, and the taxonomy, by the ecosystems, resources and hazard families the reports touch.
		Each cell shows its count; the shade deepens with the count, and a hatch marks a blind spot.
	</p>
</PageHead>

<section aria-labelledby="lanes-heading" class="block">
	<h2 id="lanes-heading">Requirements by lane</h2>
	<p class="line">
		{plural(lanes.rows.length, 'requirement')} across {plural(lanes.columns.length, 'lane')}, from {plural(
			lanes.report_ids.length,
			'active report'
		)}.
	</p>
	<Heatmap
		matrix={lanes}
		caption="Active reports by requirement and lane"
		rowHeading="Requirement"
		legend={coverage.legend}
	/>
	<p class="note">{COVERAGE_NOTES.lanes}</p>
</section>

{#each coverage.taxonomy as axis (axis.axis_id)}
	<section aria-labelledby="axis-{axis.axis_id}" class="block">
		<h2 id="axis-{axis.axis_id}">Taxonomy: {axis.axis_name}</h2>
		<p class="line">
			{plural(axis.matrix.rows.length, 'node')}, from {plural(
				axis.matrix.report_ids.length,
				'active report'
			)}.
		</p>
		<Heatmap
			matrix={axis.matrix}
			caption="Active reports by {axis.axis_name} node"
			rowHeading="Node"
			legend={coverage.legend}
			showTotal={false}
			showExpected
			showLegend={false}
		/>
		<p class="note">
			{COVERAGE_NOTES.taxonomy} Shades, hatching and statuses read as in the legend under
			<a href="#lanes-heading">Requirements by lane</a>.
		</p>
	</section>
{/each}

<section aria-labelledby="credibility-heading" class="block">
	<h2 id="credibility-heading">Credibility spread</h2>
	<div class="card">
		<CredibilityBars
			bars={coverage.credibility}
			caption="Active reports on {coverage.set_name} by credibility digit"
		/>
	</div>
	<p class="note">{COVERAGE_NOTES.credibility}</p>
</section>

<style>
	.block + .block {
		margin-top: var(--space-8);
	}

	h2 {
		margin: 0 0 var(--space-1);
		font-size: var(--text-lg);
	}

	.line {
		margin: 0 0 var(--space-3);
		color: var(--color-text-muted);
	}

	.note {
		max-width: 60rem;
		margin: var(--space-3) 0 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	.card {
		max-width: 40rem;
		padding: var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}
</style>
