import { describe, expect, it } from 'vitest';
import { snapshot } from '../../../tests/fixtures';
import { defaultProduct, markdownHref, productHref, productsByRecency } from './products';
import type { ProductSummary } from './types.generated';

const real = snapshot<ProductSummary[]>('products.json');

function product(id: string, level: ProductSummary['level'], end: string): ProductSummary {
	return {
		id,
		level,
		requirement_set_id: 'nrw-corporate-plan',
		period: { label: end.slice(0, 7), start: `${end.slice(0, 7)}-01`, end },
		generated_on: end,
		title: id,
		report_count: 1,
		section_headings: [],
		markdown_file: `${id}.md`
	};
}

describe('products', () => {
	it('opens on the latest operational product in the snapshot', () => {
		expect(defaultProduct(real)?.level).toBe('operational');
	});

	it('prefers the newest operational period over a newer strategic one', () => {
		const list = [
			product('operational-2026-09', 'operational', '2026-09-30'),
			product('strategic-2026', 'strategic', '2026-12-31'),
			product('operational-2026-10', 'operational', '2026-10-31')
		];
		expect(defaultProduct(list)?.id).toBe('operational-2026-10');
		expect(productsByRecency(list).map((p) => p.id)).toEqual([
			'strategic-2026',
			'operational-2026-10',
			'operational-2026-09'
		]);
	});

	it('falls back to the latest of any level, then to none', () => {
		expect(defaultProduct([product('strategic-2026', 'strategic', '2026-12-31')])?.id).toBe(
			'strategic-2026'
		);
		expect(defaultProduct([])).toBeNull();
	});

	it('builds the page and Markdown addresses', () => {
		expect(productHref('operational-2026-10')).toBe('/intsum/operational-2026-10');
		expect(markdownHref('operational_2026-10.md')).toBe('/products/operational_2026-10.md');
	});
});
