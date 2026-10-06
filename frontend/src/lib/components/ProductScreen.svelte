<script lang="ts" module>
	import type { Enums, ProductDetail, ProductSummary } from '$lib/data/types.generated';

	export interface ProductScreenProps {
		/** Every published product, for the selector. */
		products: ProductSummary[];
		/** The product shown, or null when none is published. */
		product: ProductDetail | null;
		enums: Enums;
	}
</script>

<script lang="ts">
	import EmptyState from './EmptyState.svelte';
	import PageHead from './PageHead.svelte';
	import ProductView from './ProductView.svelte';
	import { capitalise, enumLabel, formatDate, plural } from '$lib/data/labels';
	import { markdownHref, productHref, productsByRecency } from '$lib/data/products';

	let { products, product, enums }: ProductScreenProps = $props();

	const ordered = $derived(productsByRecency(products));
</script>

{#if product}
	<PageHead title={product.title} eyebrow="Products">
		<p>
			{capitalise(enumLabel(enums, 'product_level', product.level))} product for {product.period
				.label}, rendered on {formatDate(product.generated_on)} from {plural(
				product.report_ids.length,
				'report'
			)}.
		</p>
	</PageHead>
{:else}
	<PageHead title="Intelligence summary (INTSUM)" eyebrow="Products" />
{/if}

{#if ordered.length > 0}
	<nav class="selector" aria-label="Published products">
		<p class="selector-title">
			Published products: the monthly operational intelligence summary (INTSUM) and the annual
			strategic assessment
		</p>
		<ul>
			{#each ordered as item (item.id)}
				<li>
					<a
						href={productHref(item.id)}
						aria-current={product?.id === item.id ? 'page' : undefined}
						data-product={item.id}
					>
						<span class="level">{enumLabel(enums, 'product_level', item.level)} {item.period.label}</span>
						<span class="meta">{plural(item.report_count, 'report')}, rendered {formatDate(item.generated_on)}</span>
					</a>
				</li>
			{/each}
		</ul>
	</nav>
{/if}

{#if product}
	<p class="markdown">
		<a href={markdownHref(product.markdown_file)} download={product.markdown_file}
			>Download the Markdown ({product.markdown_file})</a
		>
		<span class="muted">Repository path: <code>data/{product.markdown_path}</code></span>
	</p>
	<ProductView {product} />
{:else}
	<EmptyState
		title="No product published yet"
		message="Products appear here once gwylio product has rendered one and the snapshot is published again."
	/>
{/if}

<style>
	.selector {
		margin-bottom: var(--space-4);
	}

	.selector-title {
		margin: 0 0 var(--space-2);
		color: var(--color-text-muted);
		font-size: var(--text-sm);
		font-weight: 600;
	}

	.selector ul {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2);
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.selector a {
		display: grid;
		padding: var(--space-2) var(--space-3);
		border: 1px solid var(--color-border);
		border-radius: var(--radius);
		background: var(--color-surface);
		color: var(--color-text);
		text-decoration: none;
		font-size: var(--text-sm);
	}

	.selector a:hover {
		border-color: var(--color-accent);
	}

	.selector a[aria-current='page'] {
		border-color: var(--color-accent);
		box-shadow: inset 0 0 0 1px var(--color-accent);
	}

	.level {
		font-weight: 700;
		text-transform: capitalize;
	}

	.meta {
		color: var(--color-text-muted);
	}

	.markdown {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-1) var(--space-4);
		margin: 0 0 var(--space-6);
		font-size: var(--text-sm);
	}

	.markdown a {
		font-weight: 600;
	}

	code {
		font-family: var(--font-mono);
		font-size: 0.9em;
	}
</style>
