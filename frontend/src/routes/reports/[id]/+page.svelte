<script lang="ts">
	import DataTable, { type Column } from '$lib/components/DataTable.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import GradingBadge from '$lib/components/GradingBadge.svelte';
	import StateChip from '$lib/components/StateChip.svelte';
	import { enumLabel, enumMeaning, formatDate, formatInstant, plural } from '$lib/data/labels';
	import type { FindingKind, SightingLine } from '$lib/data/types.generated';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const report = $derived(data.report);
	const enums = $derived(data.enums);

	/** Split prose on blank lines into paragraphs. */
	function paragraphs(text: string): string[] {
		return text
			.split(/\n\s*\n/)
			.map((p) => p.trim())
			.filter(Boolean);
	}

	function finding(...kinds: FindingKind[]) {
		return report.findings.find((f) => kinds.includes(f.kind));
	}

	const horizonFinding = $derived(finding('passed_horizon'));
	const verifiedFinding = $derived(finding('stale_verification', 'never_verified'));

	const scores = $derived([
		{ label: 'Evidence', value: enumLabel(enums, 'score_level', report.scores.evidence) },
		{ label: 'Novelty', value: enumLabel(enums, 'score_level', report.scores.novelty) },
		{ label: 'Confidence', value: enumLabel(enums, 'score_level', report.scores.confidence) },
		{
			label: 'Potential impact',
			value: enumLabel(enums, 'score_level', report.scores.potential_impact)
		},
		{ label: 'Time horizon', value: enumLabel(enums, 'time_horizon', report.scores.time_horizon) }
	]);

	const sightingColumns: Column<SightingLine>[] = [
		{ key: 'run', label: 'Run', sortValue: (s) => s.run_started_at },
		{ key: 'source', label: 'Source', sortValue: (s) => s.source_name },
		{ key: 'discipline', label: 'Discipline', sortValue: (s) => s.discipline }
	];
</script>

<svelte:head>
	<title>{report.title} | Gwylio</title>
</svelte:head>

<p class="back"><a href="/reports">All reports</a></p>

<article>
	<header class="head">
		<h1>{report.title}</h1>
		<div class="meta-row">
			<GradingBadge
				reliability={report.reliability}
				credibility={report.credibility}
				reliabilityLabel={report.reliability_label}
				credibilityLabel={report.credibility_label}
				showLabels
			/>
			<span class="pill" data-type={report.report_type}
				>type: {enumLabel(enums, 'report_type', report.report_type)}</span
			>
			<StateChip
				state={report.state}
				label="state: {enumLabel(enums, 'indicator_state', report.state)}"
				meaning={enumMeaning(enums, 'indicator_state', report.state)}
			/>
			<span class="pill" data-bucket={report.bucket}
				>bucket: {enumLabel(enums, 'bucket', report.bucket)}</span
			>
		</div>
		<p class="source">
			<a href={report.url} target="_blank" rel="noopener"
				>Open the source at {report.source_name}<span class="visually-hidden">
					(opens in a new tab)</span
				></a
			>
		</p>
	</header>

	<div class="layout">
		<div class="main">
			<section aria-labelledby="summary-heading">
				<h2 id="summary-heading">Summary</h2>
				{#each paragraphs(report.summary) as paragraph, i (i)}
					<p>{paragraph}</p>
				{/each}
			</section>

			{#if report.notes.trim()}
				<section aria-labelledby="notes-heading">
					<h2 id="notes-heading">Analyst notes</h2>
					{#each paragraphs(report.notes) as paragraph, i (i)}
						<p>{paragraph}</p>
					{/each}
				</section>
			{/if}

			<section aria-labelledby="assessments-heading">
				<h2 id="assessments-heading">Assessments</h2>
				<ul class="assessments">
					{#each report.assessments as assessment (`${assessment.set_id}:${assessment.requirement_id}`)}
						<li data-direction={assessment.direction}>
							<span class="code">{assessment.code ?? assessment.requirement_id}</span>
							<span class="req-name">{assessment.name ?? ''}</span>
							<span class="direction">
								<span class="swatch" aria-hidden="true"></span>
								{enumLabel(enums, 'direction', assessment.direction)}
							</span>
						</li>
					{/each}
				</ul>
			</section>

			<section aria-labelledby="sightings-heading">
				<h2 id="sightings-heading">Sightings</h2>
				{#if report.sightings.length === 0}
					<EmptyState
						title="No sightings recorded"
						message="No scan run has found this report's page yet; sightings appear here as runs reinforce it."
					/>
				{:else}
					<DataTable
						rows={report.sightings}
						columns={sightingColumns}
						rowKey={(s) => s.sighting_id}
						caption="Sightings of this report"
						stack
						initialSort={{ key: 'run', direction: 'descending' }}
					>
						{#snippet cell(sighting: SightingLine, column: Column<SightingLine>)}
							{#if column.key === 'run'}
								<span class="mono">{sighting.run_id}</span>
								<span class="muted">{formatInstant(sighting.run_started_at)}</span>
							{:else if column.key === 'source'}
								{sighting.source_name ?? 'open web'}
							{:else if column.key === 'discipline'}
								{sighting.discipline ? enumLabel(enums, 'discipline', sighting.discipline) : 'none'}
							{/if}
						{/snippet}
					</DataTable>
				{/if}
			</section>

			<section aria-labelledby="history-heading">
				<h2 id="history-heading">History</h2>
				<ol class="timeline">
					{#each report.history as entry, i (i)}
						<li>
							<time datetime={entry.on}>{formatDate(entry.on)}</time>
							<span class="kind">{enumLabel(enums, 'history_kind', entry.kind)}</span>
							<p class="change">{entry.change}</p>
						</li>
					{/each}
				</ol>
			</section>
		</div>

		<aside class="side">
			<section aria-labelledby="dates-heading">
				<h2 id="dates-heading">Dates</h2>
				<dl class="facts">
					<div>
						<dt>Event horizon</dt>
						<dd>
							{formatDate(report.event_horizon)}
							{#if horizonFinding}<span class="stale" title={horizonFinding.detail}>stale</span>{/if}
						</dd>
					</div>
					<div>
						<dt>Last verified</dt>
						<dd>
							{formatDate(report.last_verified, 'never')}
							{#if verifiedFinding}<span class="stale" title={verifiedFinding.detail}>stale</span
								>{/if}
						</dd>
					</div>
					<div>
						<dt>Created</dt>
						<dd>{formatDate(report.created_on)}</dd>
					</div>
					<div>
						<dt>Last changed</dt>
						<dd>{formatDate(report.last_changed)}</dd>
					</div>
				</dl>
				{#if report.findings.length > 0}
					<div class="findings">
						<p class="findings-head">Date check: {plural(report.findings.length, 'finding')}</p>
						<ul>
							{#each report.findings as f, i (i)}
								<li data-severity={f.severity}>
									<strong>{enumLabel(enums, 'finding_kind', f.kind)}</strong>: {f.detail}
								</li>
							{/each}
						</ul>
						<a href="/verify">Open the verification queue</a>
					</div>
				{/if}
			</section>

			<section aria-labelledby="scores-heading">
				<h2 id="scores-heading">Scores</h2>
				<table class="scores">
					<caption class="visually-hidden">The analyst's scores</caption>
					<tbody>
						{#each scores as score (score.label)}
							<tr>
								<th scope="row">{score.label}</th>
								<td>{score.value}</td>
							</tr>
						{/each}
					</tbody>
				</table>
			</section>

			<section aria-labelledby="tags-heading">
				<h2 id="tags-heading">Tags</h2>
				<dl class="facts">
					<div>
						<dt>Topics</dt>
						<dd>{report.topics.map((t) => t.name).join(', ') || 'none'}</dd>
					</div>
					<div>
						<dt>Hazards</dt>
						<dd>
							{report.hazards.map((h) => `${h.name} (${h.family_name})`).join(', ') || 'none'}
						</dd>
					</div>
					<div>
						<dt>Places</dt>
						<dd>{report.places.map((p) => p.name).join(', ') || 'none'}</dd>
					</div>
				</dl>
			</section>

			<section aria-labelledby="provenance-heading">
				<h2 id="provenance-heading">Provenance</h2>
				<dl class="facts">
					<div>
						<dt>Source</dt>
						<dd>{report.source_name}</dd>
					</div>
					{#if report.actor_name}
						<div>
							<dt>Actor</dt>
							<dd>{report.actor_name}</dd>
						</div>
					{/if}
					<div>
						<dt>Lane</dt>
						<dd>{report.lane_name} ({enumLabel(enums, 'lens', report.lens)} lens)</dd>
					</div>
					<div>
						<dt>Appearances</dt>
						<dd>{plural(report.appearances, 'run')}</dd>
					</div>
					<div>
						<dt>Distinct sources</dt>
						<dd>{report.distinct_sources}</dd>
					</div>
					<div>
						<dt>Independent confirmation</dt>
						<dd>{report.independent_confirmation ? 'yes' : 'no'}</dd>
					</div>
					{#if report.owner}
						<div>
							<dt>Owner</dt>
							<dd>{report.owner}</dd>
						</div>
					{/if}
					{#if report.cited_in.length > 0}
						<div>
							<dt>Cited in</dt>
							<dd>{report.cited_in.join(', ')}</dd>
						</div>
					{/if}
				</dl>
			</section>
		</aside>
	</div>
</article>

<style>
	.back {
		margin: 0 0 var(--space-3);
		font-size: var(--text-sm);
	}

	h1 {
		margin: 0 0 var(--space-3);
		font-size: var(--text-xl);
		line-height: 1.25;
	}

	.meta-row {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: var(--space-2) var(--space-3);
	}

	.pill {
		font-size: var(--text-sm);
		padding: 0 var(--space-2);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		color: var(--color-text);
		line-height: 1.6;
	}

	.source {
		margin: var(--space-3) 0 0;
		font-weight: 600;
	}

	.layout {
		display: grid;
		grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
		gap: var(--space-8);
		margin-top: var(--space-6);
	}

	section + section {
		margin-top: var(--space-6);
	}

	h2 {
		margin: 0 0 var(--space-2);
		font-size: var(--text-lg);
	}

	.main p {
		margin: 0 0 var(--space-3);
		max-width: 46rem;
	}

	.assessments {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.assessments li {
		display: grid;
		grid-template-columns: 3.5rem minmax(0, 1fr) auto;
		align-items: baseline;
		gap: var(--space-3);
		padding: var(--space-2) var(--space-3);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	.code,
	.mono {
		font-family: var(--font-mono);
		font-weight: 700;
	}

	.code {
		color: var(--color-accent);
	}

	.direction {
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		font-weight: 600;
		white-space: nowrap;
	}

	.swatch {
		width: 10px;
		height: 10px;
		border-radius: 2px;
		background: var(--seg);
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

	.timeline {
		margin: 0;
		padding: 0 0 0 var(--space-4);
		list-style: none;
		border-left: 2px solid var(--color-border);
	}

	.timeline li {
		position: relative;
		padding-bottom: var(--space-4);
	}

	.timeline li::before {
		content: '';
		position: absolute;
		left: calc(-1 * var(--space-4) - 6px);
		top: 0.45em;
		width: 10px;
		height: 10px;
		border-radius: 50%;
		background: var(--color-accent);
		box-shadow: 0 0 0 2px var(--color-bg);
	}

	.timeline time {
		font-weight: 700;
		font-variant-numeric: tabular-nums;
	}

	.kind {
		margin-left: var(--space-2);
		padding: 0 var(--space-2);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		font-size: var(--text-sm);
	}

	.timeline .change {
		margin: var(--space-1) 0 0;
		color: var(--color-text-muted);
	}

	.side section {
		padding: var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	.side section + section {
		margin-top: var(--space-4);
	}

	.side h2 {
		font-size: var(--text-md);
	}

	.facts {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		font-size: var(--text-sm);
	}

	.facts div {
		display: grid;
		grid-template-columns: 9rem minmax(0, 1fr);
		gap: var(--space-2);
	}

	dt {
		color: var(--color-text-muted);
	}

	dd {
		margin: 0;
	}

	.stale {
		margin-left: var(--space-1);
		padding: 0 var(--space-2);
		border: 1px solid var(--color-warn);
		border-radius: var(--radius);
		color: var(--color-warn);
		font-size: 0.8rem;
		font-weight: 700;
		cursor: help;
	}

	.findings {
		margin-top: var(--space-3);
		padding-top: var(--space-3);
		border-top: 1px solid var(--color-border);
		font-size: var(--text-sm);
	}

	.findings-head {
		margin: 0 0 var(--space-1);
		font-weight: 700;
	}

	.findings ul {
		margin: 0 0 var(--space-2);
		padding-left: var(--space-4);
	}

	.findings li {
		margin-bottom: var(--space-1);
	}

	.scores {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-sm);
	}

	.scores th,
	.scores td {
		padding: var(--space-1) 0;
		border-bottom: 1px solid var(--color-border);
		text-align: left;
	}

	.scores th {
		color: var(--color-text-muted);
		font-weight: 500;
	}

	.scores tr:last-child th,
	.scores tr:last-child td {
		border-bottom: 0;
	}

	@media (max-width: 860px) {
		.layout {
			grid-template-columns: minmax(0, 1fr);
			gap: var(--space-6);
		}
	}

	@media (max-width: 600px) {
		.assessments li {
			grid-template-columns: 3rem minmax(0, 1fr);
		}

		.direction {
			grid-column: 2;
		}

		.facts div {
			grid-template-columns: 7.5rem minmax(0, 1fr);
		}
	}
</style>
