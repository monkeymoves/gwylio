<script lang="ts">
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHead from '$lib/components/PageHead.svelte';
	import { enumLabel, formatInstant } from '$lib/data/labels';
	import type { RunSummary } from '$lib/data/types.generated';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const columns: Column<RunSummary>[] = [
		{ key: 'run', label: 'Run', sortValue: (r) => r.run_id },
		{ key: 'started', label: 'Started', sortValue: (r) => r.started_at },
		{ key: 'instrument', label: 'Instrument', sortValue: (r) => r.instrument_version },
		{ key: 'disciplines', label: 'Disciplines' },
		{ key: 'raw', label: 'Raw', align: 'end', sortValue: (r) => r.funnel.raw },
		{ key: 'unique', label: 'Unique', align: 'end', sortValue: (r) => r.funnel.unique },
		{ key: 'new', label: 'New', align: 'end', sortValue: (r) => r.funnel.new },
		{
			key: 'reinforcements',
			label: 'Reinforcements',
			align: 'end',
			sortValue: (r) => r.funnel.reinforcements
		},
		{ key: 'requests', label: 'Requests', align: 'end', sortValue: (r) => r.requests_made },
		{
			key: 'budget',
			label: 'Budget exhausted',
			sortValue: (r) => (r.budget_exhausted ? 0 : 1)
		},
		{ key: 'status', label: 'Status', sortValue: (r) => r.status }
	];
</script>

<PageHead title="Scans" eyebrow="Evaluation">
	<p>
		Every scan run, newest first: what its open-source intelligence (OSINT) collectors returned,
		how much survived the gates and deduplication, and how much of its request budget it spent.
		Select a run for its funnel, its sources and what the analyst did with its candidates.
	</p>
</PageHead>

{#if data.runs.length === 0}
	<EmptyState
		title="No scan runs yet"
		message="The published snapshot holds no scan run. Runs appear here once gwylio collect has run and the snapshot is published again."
	/>
{:else}
	<p class="count" data-testid="run-count">{data.runs.length} runs</p>
	<div class="runs">
		<DataTable
			rows={data.runs}
			{columns}
			rowKey={(r) => r.run_id}
			caption="Scan runs"
			initialSort={{ key: 'started', direction: 'descending' }}
			stack
			compact
		>
			{#snippet cell(run: RunSummary, column: Column<RunSummary>)}
				{#if column.key === 'run'}
					<a class="mono nowrap" href="/scans/{run.run_id}">{run.run_id}</a>
				{:else if column.key === 'started'}
					{formatInstant(run.started_at)}
				{:else if column.key === 'instrument'}
					<span class="mono">{run.instrument_version}</span>
				{:else if column.key === 'disciplines'}
					{run.disciplines.map((d) => enumLabel(data.enums, 'discipline', d)).join(', ')}
				{:else if column.key === 'raw'}
					{run.funnel.raw}
				{:else if column.key === 'unique'}
					{run.funnel.unique}
				{:else if column.key === 'new'}
					{run.funnel.new}
				{:else if column.key === 'reinforcements'}
					{run.funnel.reinforcements}
				{:else if column.key === 'requests'}
					<span class="nowrap">{run.requests_made} of {run.request_budget}</span>
				{:else if column.key === 'budget'}
					{#if run.budget_exhausted}<strong class="flag">yes</strong>{:else}no{/if}
				{:else if column.key === 'status'}
					{enumLabel(data.enums, 'run_status', run.status)}
				{/if}
			{/snippet}
		</DataTable>
	</div>
{/if}

<style>
	/* Room for "Reinforcements" as a card label at phone width. */
	.runs {
		--stack-label: 8.25rem;
	}

	.count {
		margin: 0 0 var(--space-2);
		font-weight: 600;
	}

	.mono {
		font-family: var(--font-mono);
		font-size: 0.85em;
	}

	.nowrap {
		white-space: nowrap;
	}

	.flag {
		color: var(--color-warn);
	}
</style>
