<script lang="ts">
	import { untrack } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import DirectionTags from '$lib/components/DirectionTags.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import FilterBar from '$lib/components/FilterBar.svelte';
	import GradingBadge from '$lib/components/GradingBadge.svelte';
	import StateChip from '$lib/components/StateChip.svelte';
	import {
		STATES,
		filterReports,
		parseQuery,
		serialiseQuery,
		type ReportQuery
	} from '$lib/data/filters';
	import { enumLabel, enumMeaning, formatDate, labelMap } from '$lib/data/labels';
	import { buildFilterOptions } from '$lib/data/options';
	import type { Direction, ReportSummary } from '$lib/data/types.generated';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// The prerendered page lists every report; once hydrated, the filters come
	// from the URL query string and every change is written back to it.
	let query = $state<ReportQuery>({});

	$effect(() => {
		const search = page.url.search;
		untrack(() => {
			const parsed = parseQuery(search);
			if (serialiseQuery(parsed) !== serialiseQuery(query)) query = parsed;
		});
	});

	function onchange(next: ReportQuery): void {
		query = next;
		const qs = serialiseQuery(next);
		replaceState(qs ? `${page.url.pathname}?${qs}` : page.url.pathname, page.state);
	}

	const options = $derived(buildFilterOptions(data.reports, data.enums, data.sets, data.tagNames));
	const results = $derived(filterReports(data.reports, query));
	const directionLabels = $derived(
		labelMap(data.enums, 'direction') as Partial<Record<Direction, string>>
	);

	const columns: Column<ReportSummary>[] = [
		{ key: 'grading', label: 'Grade', sortValue: (r) => r.grading },
		{ key: 'title', label: 'Report', sortValue: (r) => r.title, className: 'col-title' },
		{ key: 'directions', label: 'Directions' },
		{ key: 'state', label: 'State', sortValue: (r) => STATES.indexOf(r.state) },
		{ key: 'lane', label: 'Lane', sortValue: (r) => r.lane_name },
		{ key: 'source', label: 'Source', sortValue: (r) => r.source_name },
		{ key: 'verified', label: 'Last verified', sortValue: (r) => r.last_verified }
	];
</script>

<svelte:head>
	<title>Reports | Gwylio</title>
</svelte:head>

<header class="page-head">
	<h1>Reports</h1>
	<p class="lead">
		Every intelligence report in the register. Filter by what it bears on, how it was graded or
		where it was found; the filters stay in the address, so a filtered list can be shared.
	</p>
</header>

<FilterBar {query} {options} {onchange} />

<p class="count" role="status" aria-live="polite" data-testid="report-count">
	{results.length} of {data.reports.length} reports
</p>

{#if results.length === 0}
	<EmptyState
		title="No reports match these filters"
		message="Loosen or clear a filter to see more of the register."
	>
		<button type="button" class="clear" onclick={() => onchange({})}>Clear filters</button>
	</EmptyState>
{:else}
	<DataTable
		rows={results}
		{columns}
		rowKey={(r) => r.id}
		caption="Reports matching the filters"
		stack
	>
		{#snippet cell(report: ReportSummary, column: Column<ReportSummary>)}
			{#if column.key === 'grading'}
				<GradingBadge
					reliability={report.reliability}
					credibility={report.credibility}
					reliabilityLabel={enumLabel(data.enums, 'reliability', report.reliability)}
					credibilityLabel={enumLabel(data.enums, 'credibility', report.credibility)}
				/>
			{:else if column.key === 'title'}
				<a href="/reports/{report.id}">{report.title}</a>
			{:else if column.key === 'directions'}
				<DirectionTags assessments={report.assessments} labels={directionLabels} />
			{:else if column.key === 'state'}
				<StateChip
					state={report.state}
					label={enumLabel(data.enums, 'indicator_state', report.state)}
					meaning={enumMeaning(data.enums, 'indicator_state', report.state)}
				/>
			{:else if column.key === 'lane'}
				{report.lane_name}
			{:else if column.key === 'source'}
				{report.source_name}
			{:else if column.key === 'verified'}
				<span class="tabular nowrap">{formatDate(report.last_verified, 'never')}</span>
			{/if}
		{/snippet}
	</DataTable>
{/if}

<style>
	.page-head {
		margin-bottom: var(--space-4);
	}

	h1 {
		margin: 0 0 var(--space-2);
		font-size: var(--text-xl);
	}

	.lead {
		margin: 0;
		max-width: 60rem;
		color: var(--color-text-muted);
	}

	.count {
		margin: var(--space-4) 0 var(--space-2);
		font-weight: 600;
	}

	.nowrap {
		white-space: nowrap;
	}

	.clear {
		padding: var(--space-1) var(--space-3);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg);
		color: var(--color-text);
		font: inherit;
		font-weight: 600;
		cursor: pointer;
	}

	:global(.col-title) {
		min-width: 16rem;
	}

	@media (max-width: 600px) {
		:global(.col-title) {
			min-width: 0;
		}
	}
</style>
