<script lang="ts">
	import { FINDING_KINDS } from '$lib/components/DateCheckBanner.svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import PageHead from '$lib/components/PageHead.svelte';
	import StateChip from '$lib/components/StateChip.svelte';
	import { enumLabel, formatDate, plural } from '$lib/data/labels';
	import type { DateCheckGroup } from '$lib/data/types.generated';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const check = $derived(data.datecheck);
	const enums = $derived(data.enums);

	// Every kind, in the banner's order, even if the read model left one out.
	const groups = $derived(
		FINDING_KINDS.map(
			(kind): DateCheckGroup =>
				check.groups.find((g) => g.kind === kind) ?? {
					kind,
					severity: 'warn',
					label: enumLabel(enums, 'finding_kind', kind),
					meaning: '',
					count: 0,
					findings: []
				}
		)
	);
</script>

<PageHead title="Verify" eyebrow="Date check">
	<p>
		The verification queue. The date check looks for rot: event horizons that have passed with
		nobody looking since, future-framed language that goes stale once its date passes, and
		verifications that are old or missing. It informs and never blocks; fix a finding with an
		update or a verification in the next submission.
	</p>
</PageHead>

<p class="summary" data-testid="datecheck-summary">
	Checked on {formatDate(check.today)}: {plural(check.total, 'finding')} on {check.reports_flagged} of
	{plural(check.reports_checked, 'report')} still in the picture.
</p>

{#if check.total === 0}
	<EmptyState
		title="Nothing to verify"
		message="Every report in the picture is verified, current and written in dated terms."
	/>
{:else}
	<nav class="jump" aria-label="Finding kinds">
		<ul>
			{#each groups as group (group.kind)}
				<li><a href="#{group.kind}">{group.label} <span class="n">{group.count}</span></a></li>
			{/each}
		</ul>
	</nav>

	{#each groups as group (group.kind)}
		<section class="group" id={group.kind} aria-labelledby="{group.kind}-heading" data-kind={group.kind}>
			<header class="group-head">
				<h2 id="{group.kind}-heading">{group.label}</h2>
				<span class="severity" data-severity={group.severity}
					>{group.severity === 'act' ? 'act before quoting' : 'check'}</span
				>
			</header>
			<p class="count-line" data-testid="count-{group.kind}">
				{plural(group.count, 'finding')}{group.meaning ? `. ${group.meaning}` : ''}
			</p>
			{#if group.findings.length > 0}
				<ol class="findings">
					{#each group.findings as finding, i (`${finding.report_id}:${i}`)}
						<li>
							<div class="title-row">
								<a href="/reports/{finding.report_id}">{finding.title}</a>
								<StateChip
									state={finding.state}
									label={enumLabel(enums, 'indicator_state', finding.state)}
								/>
							</div>
							<p class="detail">{finding.detail}</p>
						</li>
					{/each}
				</ol>
			{/if}
		</section>
	{/each}
{/if}

<style>
	.summary {
		margin: 0 0 var(--space-4);
		font-weight: 600;
	}

	.jump ul {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		margin: 0 0 var(--space-6);
		padding: 0;
		list-style: none;
		font-size: var(--text-sm);
	}

	.jump a {
		display: inline-flex;
		gap: var(--space-1);
		padding: var(--space-1) var(--space-3);
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface);
		text-decoration: none;
		font-weight: 600;
	}

	.n {
		color: var(--color-text);
		font-variant-numeric: tabular-nums;
	}

	.group + .group {
		margin-top: var(--space-8);
	}

	.group-head {
		display: flex;
		flex-wrap: wrap;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
	}

	h2 {
		margin: 0;
		font-size: var(--text-lg);
	}

	.severity {
		padding: 0 var(--space-2);
		border: 1px solid currentColor;
		border-radius: var(--radius);
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--color-warn);
	}

	.severity[data-severity='act'] {
		color: var(--color-bad);
	}

	.count-line {
		margin: var(--space-1) 0 var(--space-3);
		max-width: 60rem;
		color: var(--color-text-muted);
	}

	.findings {
		display: grid;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.findings li {
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	.title-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: baseline;
		gap: var(--space-1) var(--space-3);
	}

	.title-row a {
		font-weight: 600;
	}

	.detail {
		margin: var(--space-1) 0 0;
		color: var(--color-text-muted);
		font-size: var(--text-sm);
	}

	@media (max-width: 600px) {
		.findings li {
			padding: var(--space-3);
		}
	}
</style>
