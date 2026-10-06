<script lang="ts">
	import PageHead from '$lib/components/PageHead.svelte';
	import { ABOUT } from '$lib/content/about';
</script>

<PageHead title={ABOUT.title} eyebrow="About">
	{#each ABOUT.lead as paragraph, i (i)}
		<p>{paragraph}</p>
	{/each}
</PageHead>

<nav class="contents" aria-label="On this page">
	<ol>
		{#each ABOUT.sections as section (section.id)}
			<li><a href="#{section.id}">{section.heading}</a></li>
		{/each}
	</ol>
</nav>

{#each ABOUT.sections as section (section.id)}
	<section id={section.id} aria-labelledby="{section.id}-heading">
		<h2 id="{section.id}-heading">{section.heading}</h2>
		{#each section.paragraphs as paragraph, i (i)}
			<p>{paragraph}</p>
		{/each}
		{#if section.list}
			<svelte:element this={section.list.ordered ? 'ol' : 'ul'} class="list">
				{#each section.list.items as item, i (i)}
					<li>{#if item.term}<strong>{item.term}</strong>{' '}{/if}{item.text}</li>
				{/each}
			</svelte:element>
		{/if}
		{#each section.tables ?? [] as table (table.caption)}
			<div class="table-scroll">
				<table>
					<caption>{table.caption}</caption>
					<thead>
						<tr>
							{#each table.headers as header (header)}
								<th scope="col">{header}</th>
							{/each}
						</tr>
					</thead>
					<tbody>
						{#each table.rows as row (row[0])}
							<tr>
								{#each row as cell, c (c)}
									{#if c === 0}
										<th scope="row" class="key">{cell}</th>
									{:else}
										<td>{cell}</td>
									{/if}
								{/each}
							</tr>
						{/each}
					</tbody>
				</table>
			</div>
		{/each}
		{#each section.after ?? [] as paragraph, i (i)}
			<p>{paragraph}</p>
		{/each}
	</section>
{/each}

<style>
	.contents ol {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0 0 var(--space-6);
		padding: 0;
		list-style: none;
		font-size: var(--text-sm);
		font-weight: 600;
	}

	section {
		max-width: 52rem;
	}

	section + section {
		margin-top: var(--space-8);
	}

	h2 {
		margin: 0 0 var(--space-2);
		font-size: var(--text-lg);
	}

	p {
		margin: 0 0 var(--space-3);
	}

	.list {
		margin: 0 0 var(--space-3);
		padding-left: var(--space-6);
	}

	.list li {
		margin-bottom: var(--space-2);
	}

	.table-scroll {
		width: 100%;
		margin: 0 0 var(--space-4);
		overflow-x: auto;
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
	}

	table {
		width: 100%;
		border-collapse: collapse;
		font-size: var(--text-sm);
		overflow-wrap: normal;
	}

	caption {
		padding: var(--space-2) var(--space-3);
		font-weight: 700;
		text-align: left;
	}

	th,
	td {
		padding: var(--space-2) var(--space-3);
		border-top: 1px solid var(--color-border);
		text-align: left;
		vertical-align: top;
	}

	thead th {
		color: var(--color-text-muted);
		font-weight: 600;
	}

	.key {
		font-family: var(--font-mono);
		font-weight: 700;
		white-space: nowrap;
	}
</style>
