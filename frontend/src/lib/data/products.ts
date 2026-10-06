/**
 * Which product the intelligence summary page opens on, and where each
 * product and its Markdown live in the static site. Pure.
 */
import type { ProductLevel, ProductSummary } from './types.generated';

/** Products of a level, newest period first (ties broken by render date, then id). */
export function productsByRecency(
	products: readonly ProductSummary[],
	level?: ProductLevel
): ProductSummary[] {
	return products
		.filter((p) => level === undefined || p.level === level)
		.slice()
		.sort(
			(a, b) =>
				b.period.end.localeCompare(a.period.end) ||
				b.generated_on.localeCompare(a.generated_on) ||
				a.id.localeCompare(b.id)
		);
}

/**
 * The product the page opens on: the latest operational intelligence summary
 * (INTSUM), or the latest product of any level when there is no INTSUM yet.
 */
export function defaultProduct(products: readonly ProductSummary[]): ProductSummary | null {
	return productsByRecency(products, 'operational')[0] ?? productsByRecency(products)[0] ?? null;
}

/** The page that renders one product. */
export function productHref(productId: string): string {
	return `/intsum/${encodeURIComponent(productId)}`;
}

/** The product's Markdown as the static site serves it (prerendered from the snapshot). */
export function markdownHref(markdownFile: string): string {
	return `/products/${encodeURIComponent(markdownFile)}`;
}
