<script lang="ts" module>
	import type { ProductDetail, SectionModel } from '$lib/data/types.generated';

	export interface ProductViewProps {
		product: ProductDetail;
	}

	/** The heading element for a section: depth 2 is h2, 3 is h3, clamped to h2 to h4. */
	export function headingTag(section: SectionModel): 'h2' | 'h3' | 'h4' {
		if (section.depth <= 2) return 'h2';
		if (section.depth === 3) return 'h3';
		return 'h4';
	}

	/** Above this many columns a product table is set tighter to fit the reading column. */
	export const WIDE_TABLE_COLUMNS = 6;
</script>

<script lang="ts">
	let { product }: ProductViewProps = $props();
</script>

<article class="product" data-product={product.id}>
	{#each product.lead as paragraph, i (i)}
		<p class="lead">{paragraph}</p>
	{/each}

	{#each product.sections as section, i (i)}
		<section class="depth-{Math.min(Math.max(section.depth, 2), 4)}">
			<svelte:element this={headingTag(section)}>{section.heading}</svelte:element>
			{#each section.body as paragraph, j (j)}
				<p>{paragraph}</p>
			{/each}
			{#each section.tables as table, t (t)}
				<div class="table-scroll">
					<table class:wide={table.headers.length > WIDE_TABLE_COLUMNS}>
						<thead>
							<tr>
								{#each table.headers as header, h (h)}
									<th scope="col">{header}</th>
								{/each}
							</tr>
						</thead>
						<tbody>
							{#each table.rows as row, r (r)}
								<tr>
									{#each row as cell, c (c)}
										<td>{cell}</td>
									{/each}
								</tr>
							{/each}
						</tbody>
					</table>
				</div>
			{/each}
			{#if section.bullets.length > 0}
				<ul>
					{#each section.bullets as bullet, b (b)}
						<li>{bullet}</li>
					{/each}
				</ul>
			{/if}
		</section>
	{/each}
</article>

<style>
	.product {
		max-width: 52rem;
	}

	.lead {
		margin: 0 0 var(--space-3);
		color: var(--color-text-muted);
	}

	section {
		margin-top: var(--space-6);
	}

	section.depth-3,
	section.depth-4 {
		margin-top: var(--space-4);
	}

	h2,
	h3,
	h4 {
		margin: 0 0 var(--space-2);
		line-height: 1.3;
	}

	h2 {
		font-size: var(--text-lg);
	}

	h3,
	h4 {
		font-size: var(--text-md);
	}

	p {
		margin: 0 0 var(--space-3);
	}

	ul {
		margin: 0 0 var(--space-3);
		padding-left: var(--space-6);
	}

	li {
		margin-bottom: var(--space-1);
	}

	.table-scroll {
		width: 100%;
		margin: 0 0 var(--space-3);
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

	th,
	td {
		padding: var(--space-2) var(--space-3);
		border-bottom: 1px solid var(--color-border);
		text-align: left;
		vertical-align: top;
	}

	th {
		color: var(--color-text-muted);
		font-weight: 600;
	}

	/* A wide table (such as the method note's runs, nine columns) is set smaller with
	   tighter cells, so it fits the reading column at desktop width without breaking words. */
	table.wide {
		font-size: var(--text-xs);
	}

	table.wide th,
	table.wide td {
		padding: var(--space-2);
	}

	tbody tr:last-child td {
		border-bottom: 0;
	}
</style>
