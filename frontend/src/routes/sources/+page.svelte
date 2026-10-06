<script lang="ts">
	import { untrack } from 'svelte';
	import { replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import FunnelTrend from '$lib/components/FunnelTrend.svelte';
	import PageHead from '$lib/components/PageHead.svelte';
	import { enumLabel, enumMeaning, plural } from '$lib/data/labels';
	import {
		READING_ORDER,
		SOURCE_SORT,
		filterSources,
		laneOptions,
		parseSourceQuery,
		serialiseSourceQuery,
		silentSources,
		type SourceColumnKey,
		type SourceQuery
	} from '$lib/data/sources';
	import type { SourceSummary } from '$lib/data/types.generated';
	import { formatRate } from '$lib/data/viz';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	// The prerendered page lists every source; once hydrated, the lane filter
	// comes from the URL query string and every change is written back to it.
	let query = $state<SourceQuery>({});

	$effect(() => {
		const search = page.url.search;
		untrack(() => {
			const parsed = parseSourceQuery(search);
			if (serialiseSourceQuery(parsed) !== serialiseSourceQuery(query)) query = parsed;
		});
	});

	function setLane(lane: string): void {
		const next: SourceQuery = lane ? { lane } : {};
		query = next;
		const qs = serialiseSourceQuery(next);
		replaceState(qs ? `${page.url.pathname}?${qs}` : page.url.pathname, page.state);
	}

	const lanes = $derived(laneOptions(data.sources));
	const rows = $derived(filterSources(data.sources, query));
	const silent = $derived(silentSources(data.health, data.sources));
	const health = $derived(data.health);

	function column(
		key: SourceColumnKey,
		label: string,
		extra: Partial<Column<SourceSummary>> = {}
	): Column<SourceSummary> {
		return { key, label, sortValue: SOURCE_SORT[key], ...extra };
	}

	const columns: Column<SourceSummary>[] = [
		column('name', 'Source', { className: 'col-name' }),
		column('lane', 'Lane'),
		column('discipline', 'Discipline'),
		column('reliability', 'Reliability'),
		column('status', 'Status'),
		column('trusted', 'Trusted'),
		column('raw_hits', 'Raw hits', { align: 'end' }),
		column('unique_candidates', 'Unique candidates', { align: 'end' }),
		column('promoted', 'Promoted', { align: 'end' }),
		column('promotion_rate', 'Promotion rate', { align: 'end' }),
		column('last_productive_run', 'Last productive run'),
		column('reading', 'Reading')
	];
</script>

<PageHead title="Sources" eyebrow="Evaluation">
	<p>
		The watchlist: every source the open-source intelligence (OSINT) scan reads, with its
		Admiralty reliability letter and what it has yielded. Raw hits are the hits that passed the gates; a promotion is a candidate the
		analyst turned into an intelligence report.
	</p>
</PageHead>

<section aria-labelledby="readings-heading" class="block">
	<h2 id="readings-heading">Readings</h2>
	<p class="line">
		{plural(health.sources, 'source')} on the watchlist, {health.active_sources} active; {plural(
			health.runs_total,
			'scan run'
		)} recorded.
	</p>
	<ul class="readings" aria-label="Sources by yield reading">
		{#each READING_ORDER as reading (reading)}
			<li title={enumMeaning(data.enums, 'yield_reading', reading) ?? undefined}>
				<span class="count">{health.readings[reading]}</span>
				{enumLabel(data.enums, 'yield_reading', reading)}
			</li>
		{/each}
	</ul>
</section>

<section aria-labelledby="watchlist-heading" class="block">
	<h2 id="watchlist-heading">Watchlist</h2>
	<form class="filter" onsubmit={(event) => event.preventDefault()}>
		<label for="lane-filter">Lane</label>
		<select
			id="lane-filter"
			name="lane"
			value={query.lane ?? ''}
			onchange={(event) => setLane(event.currentTarget.value)}
		>
			<option value="">Any lane</option>
			{#each lanes as option (option.value)}
				<option value={option.value}>{option.label}</option>
			{/each}
		</select>
		<button type="button" disabled={!query.lane} onclick={() => setLane('')}>Clear</button>
	</form>
	<p class="count" role="status" aria-live="polite" data-testid="source-count">
		{rows.length} of {data.sources.length} sources
	</p>
	{#if rows.length === 0}
		<EmptyState title="No sources in this lane" message="Choose another lane or clear the filter.">
			<button type="button" class="clear" onclick={() => setLane('')}>Clear the filter</button>
		</EmptyState>
	{:else}
		<DataTable
			{rows}
			{columns}
			rowKey={(s) => s.id}
			caption="Watched sources and their yield"
			initialSort={{ key: 'name', direction: 'ascending' }}
			stack
			compact
		>
			{#snippet cell(source: SourceSummary, col: Column<SourceSummary>)}
				{#if col.key === 'name'}
					<span class="source"
						><span class="name">{source.name}</span><span class="domain">{source.domain}</span></span
					>
				{:else if col.key === 'lane'}
					{source.lane_name}
				{:else if col.key === 'discipline'}
					{enumLabel(data.enums, 'discipline', source.discipline)}
				{:else if col.key === 'reliability'}
					<abbr class="letter" title="{source.reliability}: {source.reliability_label}"
						>{source.reliability}</abbr
					>
				{:else if col.key === 'status'}
					{enumLabel(data.enums, 'source_status', source.status)}
				{:else if col.key === 'trusted'}
					{source.trusted ? 'yes' : 'no'}
				{:else if col.key === 'raw_hits'}
					{source.raw_hits}
				{:else if col.key === 'unique_candidates'}
					{source.unique_candidates}
				{:else if col.key === 'promoted'}
					{source.promoted}
				{:else if col.key === 'promotion_rate'}
					{formatRate(source.promotion_rate)}
				{:else if col.key === 'last_productive_run'}
					{#if source.last_productive_run}
						<a class="mono" href="/scans/{source.last_productive_run}">{source.last_productive_run}</a>
					{:else}
						<span class="muted">none</span>
					{/if}
				{:else if col.key === 'reading'}
					<span
						class="reading"
						data-reading={source.reading}
						title={enumMeaning(data.enums, 'yield_reading', source.reading) ?? undefined}
						>{enumLabel(data.enums, 'yield_reading', source.reading)}</span
					>
				{/if}
			{/snippet}
		</DataTable>
	{/if}
</section>

<section aria-labelledby="silent-heading" class="block">
	<h2 id="silent-heading">Silent sources</h2>
	{#if silent.length === 0}
		<p class="line">Every active source has returned at least one hit.</p>
	{:else}
		<p class="line" data-testid="silent-count">
			{#if health.runs_total === 0}
				No scan run is recorded yet, so all {silent.length} of {health.active_sources} active sources
				read silent.
			{:else}
				{silent.length} of {health.active_sources} active sources have returned no hit in {plural(
					health.runs_total,
					'scan run'
				)}.
			{/if}
		</p>
		<ul class="silent">
			{#each silent as source (source.id)}
				<li>
					<span class="name">{source.name}</span>
					{#if source.lane_name}<span class="muted">{source.lane_name}</span>{/if}
				</li>
			{/each}
		</ul>
	{/if}
</section>

<section aria-labelledby="trend-heading" class="block">
	<h2 id="trend-heading">Funnel trend</h2>
	{#if health.trend.length === 0}
		<EmptyState
			title="No scan runs yet"
			message="The trend shows raw hits, unique candidates, new candidates and reinforcements for each of the last {health.window} runs once a run is published."
		/>
	{:else}
		<p class="line">
			The last {plural(health.trend.length, 'run')} of {health.runs_total}, oldest first.
		</p>
		<FunnelTrend trend={health.trend} />
	{/if}
</section>

<style>
	.block + .block {
		margin-top: var(--space-8);
	}

	h2 {
		margin: 0 0 var(--space-2);
		font-size: var(--text-lg);
	}

	.line {
		margin: 0 0 var(--space-3);
		color: var(--color-text-muted);
	}

	.readings {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.readings li {
		padding: var(--space-1) var(--space-3);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		font-size: var(--text-sm);
		cursor: help;
	}

	.readings .count {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.filter {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-3);
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	.filter label {
		color: var(--color-text-muted);
		font-size: var(--text-sm);
		font-weight: 600;
	}

	.filter select,
	.filter button,
	.clear {
		min-height: 2.25rem;
		padding: var(--space-1) var(--space-2);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-bg);
		color: var(--color-text);
		font: inherit;
		font-size: var(--text-sm);
	}

	.filter select {
		flex: 1 1 14rem;
		max-width: 24rem;
		min-width: 0;
	}

	.filter button,
	.clear {
		font-weight: 600;
		cursor: pointer;
	}

	.filter button:disabled {
		color: var(--color-text-muted);
		cursor: default;
	}

	.count {
		margin: var(--space-3) 0 var(--space-2);
		font-weight: 600;
	}

	.name {
		display: block;
		font-weight: 600;
	}

	.domain {
		display: block;
		color: var(--color-text-muted);
		font-size: 0.8rem;
	}

	.letter {
		font-family: var(--font-mono);
		font-weight: 700;
		text-decoration: underline dotted;
		cursor: help;
	}

	.mono {
		font-family: var(--font-mono);
		font-size: 0.85em;
	}

	.reading {
		cursor: help;
	}

	.reading[data-reading='silent'] {
		color: var(--color-text-muted);
	}

	.silent {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(16rem, 1fr));
		gap: var(--space-1) var(--space-4);
		margin: 0;
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		list-style: none;
		font-size: var(--text-sm);
	}

	.silent li {
		display: grid;
		align-content: start;
	}

	.silent .name {
		font-weight: 600;
	}

	.silent .muted {
		font-size: 0.8rem;
	}

	.source {
		display: grid;
	}

	:global(.col-name) {
		min-width: 10rem;
	}


	@media (max-width: 600px) {
		:global(.col-name) {
			min-width: 0;
		}

		.filter {
			padding: var(--space-3);
		}

		.silent {
			grid-template-columns: minmax(0, 1fr);
			padding: var(--space-3);
		}
	}
</style>
