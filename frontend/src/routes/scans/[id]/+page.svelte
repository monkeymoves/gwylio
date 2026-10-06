<script lang="ts">
	import CredibilityBars from '$lib/components/CredibilityBars.svelte';
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import FunnelDiagram from '$lib/components/FunnelDiagram.svelte';
	import PageHead from '$lib/components/PageHead.svelte';
	import { enumLabel, enumMeaning, formatInstant, plural } from '$lib/data/labels';
	import type {
		DispositionOutcome,
		DisciplineCount,
		SourceCount
	} from '$lib/data/types.generated';
	import { formatRate } from '$lib/data/viz';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const run = $derived(data.run);
	const enums = $derived(data.enums);

	const OUTCOMES: readonly DispositionOutcome[] = [
		'promoted',
		'reinforcement',
		'duplicate',
		'rejected',
		'deferred'
	];

	const sourceColumns: Column<SourceCount>[] = [
		{ key: 'source', label: 'Source', sortValue: (s) => s.source_name ?? '' },
		{ key: 'sightings', label: 'Sightings', align: 'end', sortValue: (s) => s.sightings },
		{ key: 'candidates', label: 'Candidates found first', align: 'end', sortValue: (s) => s.candidates }
	];

	const disciplineColumns: Column<DisciplineCount>[] = [
		{ key: 'discipline', label: 'Discipline' },
		{ key: 'sightings', label: 'Sightings', align: 'end' },
		{ key: 'candidates', label: 'Candidates', align: 'end' }
	];
</script>

<PageHead title="Scan run {run.run_id}" eyebrow="Scan">
	<p>
		Started {formatInstant(run.started_at)}{#if run.finished_at}, finished {formatInstant(
				run.finished_at
			)}{/if}. Status: {enumLabel(enums, 'run_status', run.status)}. The disciplines are the kinds
		of open-source intelligence (OSINT) collection the run used.
	</p>
</PageHead>

<p class="back"><a href="/scans">All scan runs</a></p>

<dl class="facts">
	<div>
		<dt>Instrument</dt>
		<dd><span class="mono">{run.instrument_version}</span></dd>
	</div>
	<div>
		<dt>Disciplines</dt>
		<dd>{run.disciplines.map((d) => enumLabel(enums, 'discipline', d)).join(', ')}</dd>
	</div>
	<div>
		<dt>Requests</dt>
		<dd>
			{run.requests_made} of a budget of {run.request_budget}{#if run.budget_exhausted}
				<strong class="flag">budget exhausted</strong>{/if}
		</dd>
	</div>
	<div>
		<dt>Candidates</dt>
		<dd>{run.candidates}</dd>
	</div>
	<div>
		<dt>Submissions</dt>
		<dd>{run.submissions.length > 0 ? run.submissions.join(', ') : 'none yet'}</dd>
	</div>
</dl>

<div class="layout">
	<section aria-labelledby="funnel-heading" class="card">
		<h2 id="funnel-heading">Funnel</h2>
		<FunnelDiagram funnel={run.funnel} caption="Funnel of run {run.run_id}" />
	</section>

	<section aria-labelledby="dispositions-heading" class="card">
		<h2 id="dispositions-heading">Dispositions</h2>
		<p class="line">
			{run.dispositions.disposed} of {plural(run.dispositions.new, 'new candidate')} judged;
			{run.dispositions.undisposed} waiting. Promotion rate: {formatRate(
				run.dispositions.promotion_rate
			)}.
		</p>
		<table class="outcomes">
			<caption class="visually-hidden">Candidates by final disposition</caption>
			<tbody>
				{#each OUTCOMES as outcome (outcome)}
					<tr data-outcome={outcome}>
						<th scope="row" title={enumMeaning(enums, 'disposition_outcome', outcome) ?? undefined}
							>{enumLabel(enums, 'disposition_outcome', outcome)}</th
						>
						<td>{run.dispositions.counts[outcome]}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		{#if run.promoted_report_ids.length > 0}
			<h3>Reports this run created</h3>
			<ul class="links">
				{#each run.promoted_report_ids as id (id)}
					<li><a href="/reports/{id}">{id}</a></li>
				{/each}
			</ul>
		{/if}
	</section>

	<section aria-labelledby="credibility-heading" class="card">
		<h2 id="credibility-heading">Credibility of the promotions</h2>
		<CredibilityBars
			bars={run.credibility}
			caption="Reports created by run {run.run_id}, by credibility digit"
			unit="promotion"
		/>
	</section>

	<section aria-labelledby="warnings-heading" class="card">
		<h2 id="warnings-heading">Warnings and notes</h2>
		{#if run.warnings.length === 0 && run.notes.length === 0}
			<p class="line">The collectors raised no warning and the run recorded no note.</p>
		{:else}
			<ul class="warnings">
				{#each run.warnings as warning, i (i)}
					<li data-kind="warning"><strong>Warning:</strong> {warning}</li>
				{/each}
				{#each run.notes as note, i (i)}
					<li data-kind="note"><strong>Note:</strong> {note}</li>
				{/each}
			</ul>
		{/if}
	</section>
</div>

<section aria-labelledby="sources-heading" class="block">
	<h2 id="sources-heading">By source</h2>
	<DataTable
		rows={run.per_source}
		columns={sourceColumns}
		rowKey={(s) => s.source_id ?? 'open-web'}
		caption="Sightings and candidates by source in this run"
		initialSort={{ key: 'sightings', direction: 'descending' }}
		stack
	>
		{#snippet cell(source: SourceCount, column: Column<SourceCount>)}
			{#if column.key === 'source'}
				{source.source_name ?? 'open web (no watched source)'}
			{:else if column.key === 'sightings'}
				{source.sightings}
			{:else if column.key === 'candidates'}
				{source.candidates}
			{/if}
		{/snippet}
	</DataTable>
</section>

<section aria-labelledby="disciplines-heading" class="block">
	<h2 id="disciplines-heading">By discipline</h2>
	<DataTable
		rows={run.per_discipline}
		columns={disciplineColumns}
		rowKey={(d) => d.discipline}
		caption="Sightings and candidates by discipline in this run"
	>
		{#snippet cell(row: DisciplineCount, column: Column<DisciplineCount>)}
			{#if column.key === 'discipline'}
				{enumLabel(enums, 'discipline', row.discipline)}
			{:else if column.key === 'sightings'}
				{row.sightings}
			{:else if column.key === 'candidates'}
				{row.candidates}
			{/if}
		{/snippet}
	</DataTable>
</section>

<style>
	.back {
		margin: 0 0 var(--space-4);
		font-size: var(--text-sm);
	}

	.facts {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2) var(--space-6);
		margin: 0 0 var(--space-6);
		font-size: var(--text-sm);
	}

	.facts div {
		display: grid;
	}

	dt {
		color: var(--color-text-muted);
	}

	dd {
		margin: 0;
		font-weight: 600;
	}

	.mono {
		font-family: var(--font-mono);
	}

	.flag {
		margin-left: var(--space-1);
		color: var(--color-warn);
	}

	.layout {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(min(100%, 26rem), 1fr));
		gap: var(--space-4);
	}

	.card {
		padding: var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		min-width: 0;
	}

	.block {
		margin-top: var(--space-8);
	}

	h2 {
		margin: 0 0 var(--space-3);
		font-size: var(--text-lg);
	}

	h3 {
		margin: var(--space-3) 0 var(--space-1);
		font-size: var(--text-md);
	}

	.line {
		margin: 0 0 var(--space-3);
		color: var(--color-text-muted);
	}

	.outcomes {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-sm);
	}

	.outcomes th,
	.outcomes td {
		padding: var(--space-1) 0;
		border-bottom: 1px solid var(--color-border);
		text-align: left;
	}

	.outcomes th {
		font-weight: 500;
		cursor: help;
	}

	.outcomes td {
		text-align: right;
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.outcomes tr:last-child th,
	.outcomes tr:last-child td {
		border-bottom: 0;
	}

	.links,
	.warnings {
		margin: 0;
		padding-left: var(--space-4);
		font-size: var(--text-sm);
	}

	.warnings li {
		margin-bottom: var(--space-1);
	}
</style>
