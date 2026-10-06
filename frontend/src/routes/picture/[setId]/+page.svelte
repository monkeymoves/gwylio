<script lang="ts">
	import CoverageChip from '$lib/components/CoverageChip.svelte';
	import DateCheckBanner from '$lib/components/DateCheckBanner.svelte';
	import GroupTile from '$lib/components/GroupTile.svelte';
	import RequirementTile from '$lib/components/RequirementTile.svelte';
	import { serialiseQuery } from '$lib/data/filters';
	import { formatDate } from '$lib/data/labels';
	import type { CoverageStatus, GroupTile as GroupTileModel } from '$lib/data/types.generated';
	import type { PageData } from './$types';

	let { data }: { data: PageData } = $props();

	const picture = $derived(data.picture);
	const enums = $derived(data.enums);
	const codes = $derived(new Map(picture.requirements.map((r) => [r.requirement_id, r.code])));
	const notes = $derived(new Map(data.set.groups.map((g) => [g.id, g.note])));
	const scanabilityNotes = $derived(
		new Map(data.set.requirements.map((r) => [r.id, r.scanability_note]))
	);

	function reportsHref(requirementId: string): string {
		return `/reports?${serialiseQuery({ requirement: requirementId })}`;
	}

	function members(group: GroupTileModel) {
		return group.members.map((id) => ({
			id,
			code: codes.get(id) ?? id.toUpperCase(),
			href: reportsHref(id)
		}));
	}
</script>

<svelte:head>
	<title>Picture: {picture.set_name} | Gwylio</title>
</svelte:head>

<header class="page-head">
	<p class="eyebrow">Picture</p>
	<h1>{picture.set_name}</h1>
	<p class="lead">
		This intelligence picture counts the reports in the register assessed against this
		requirement set, as at {formatDate(picture.today)} (set version: {picture.version}).
		{enums.undercount}
	</p>
</header>

<DateCheckBanner counts={picture.datecheck} {enums} />

<section aria-labelledby="wbo-heading">
	<h2 id="wbo-heading">Well-being objectives</h2>
	<p class="explain">
		Each well-being objective (WBO) gathers the requirements that serve it. Its bar counts the
		active reports on any member, once per direction, so a report that cuts both ways appears
		under both.
	</p>
	<ul class="grid groups">
		{#each picture.wbo_groups as group (group.group_id)}
			<li>
				<GroupTile {group} {enums} members={members(group)} note={notes.get(group.group_id)} />
			</li>
		{/each}
	</ul>
</section>

<section aria-labelledby="impact-heading">
	<h2 id="impact-heading">Impacts</h2>
	<p class="explain">
		Each impact is an outcome the set aims for, in its own words. Its bar counts the active
		reports on its member requirements in the same way.
	</p>
	<ul class="grid groups">
		{#each picture.impact_groups as group (group.group_id)}
			<li>
				<GroupTile {group} {enums} members={members(group)} note={notes.get(group.group_id)} />
			</li>
		{/each}
	</ul>
</section>

<section aria-labelledby="requirement-heading">
	<h2 id="requirement-heading">Requirements</h2>
	<p class="explain">
		Each requirement is one priority intelligence requirement (PIR) in the set. Its bar splits
		the active reports by direction; select a tile to list its reports.
	</p>
	<div class="legend">
		<ul aria-label="Coverage status">
			{#each enums.coverage_status as entry (entry.value)}
				<li>
					<span><CoverageChip status={entry.value as CoverageStatus} label={entry.label} /></span>
					<span class="meaning">{entry.meaning}</span>
				</li>
			{/each}
		</ul>
		<p class="rule">{enums.blind_spot_rule}</p>
	</div>
	<ul class="grid requirements">
		{#each picture.requirements as tile (tile.requirement_id)}
			<li>
				<RequirementTile
					{tile}
					{enums}
					href={reportsHref(tile.requirement_id)}
					scanabilityNote={scanabilityNotes.get(tile.requirement_id)}
				/>
			</li>
		{/each}
	</ul>
</section>

<style>
	.page-head {
		margin-bottom: var(--space-6);
	}

	.eyebrow {
		margin: 0;
		color: var(--color-accent);
		font-size: var(--text-sm);
		font-weight: 700;
		letter-spacing: 0.04em;
		text-transform: uppercase;
	}

	h1 {
		margin: var(--space-1) 0 var(--space-2);
		font-size: var(--text-xl);
		line-height: 1.2;
	}

	.lead {
		margin: 0;
		max-width: 60rem;
		color: var(--color-text-muted);
	}

	section {
		margin-top: var(--space-8);
	}

	h2 {
		margin: 0 0 var(--space-1);
		font-size: var(--text-lg);
	}

	.explain {
		margin: 0 0 var(--space-4);
		max-width: 60rem;
		color: var(--color-text-muted);
	}

	.grid {
		display: grid;
		gap: var(--space-4);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.grid > li {
		min-width: 0;
	}

	.groups {
		grid-template-columns: repeat(auto-fill, minmax(20rem, 1fr));
	}

	.requirements {
		grid-template-columns: repeat(auto-fill, minmax(17rem, 1fr));
	}

	.legend {
		margin-bottom: var(--space-4);
		padding: var(--space-3) var(--space-4);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		font-size: var(--text-sm);
	}

	.legend ul {
		display: grid;
		grid-template-columns: max-content minmax(0, 1fr);
		align-items: baseline;
		gap: var(--space-2) var(--space-3);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.legend li {
		display: contents;
	}

	.meaning {
		color: var(--color-text-muted);
	}

	.rule {
		margin: var(--space-3) 0 0;
		font-weight: 600;
	}

	@media (max-width: 600px) {
		.groups,
		.requirements {
			grid-template-columns: minmax(0, 1fr);
		}

		.legend ul {
			grid-template-columns: minmax(0, 1fr);
			gap: var(--space-1);
		}

		.meaning {
			margin-bottom: var(--space-2);
		}
	}
</style>
