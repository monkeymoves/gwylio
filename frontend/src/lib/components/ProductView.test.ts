import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { snapshot } from '../../../tests/fixtures';
import type { ProductDetail } from '$lib/data/types.generated';
import ProductView, { headingTag } from './ProductView.svelte';

const intsum = snapshot<ProductDetail>('products/operational-2026-10.json');

describe('ProductView', () => {
	it('renders every section heading at its depth', () => {
		render(ProductView, { product: intsum });
		for (const section of intsum.sections) {
			const level = Number(headingTag(section).slice(1));
			expect(screen.getAllByRole('heading', { level, name: section.heading }).length).toBeGreaterThan(0);
		}
	});

	it('renders the lead, paragraphs, bullets and tables', () => {
		const { container } = render(ProductView, { product: intsum });
		for (const paragraph of intsum.lead) expect(screen.getByText(paragraph)).toBeInTheDocument();
		const bullets = intsum.sections.flatMap((s) => s.bullets);
		expect(container.querySelectorAll('li')).toHaveLength(bullets.length);
		const tables = intsum.sections.flatMap((s) => s.tables);
		expect(container.querySelectorAll('table')).toHaveLength(tables.length);
		const first = tables[0];
		if (first) {
			expect(screen.getAllByRole('columnheader').map((th) => th.textContent)).toEqual(
				expect.arrayContaining(first.headers)
			);
		}
	});

	it('clamps unusual depths to h2 to h4', () => {
		const section = { heading: 'X', depth: 1, body: [], tables: [], bullets: [] };
		expect(headingTag(section)).toBe('h2');
		expect(headingTag({ ...section, depth: 3 })).toBe('h3');
		expect(headingTag({ ...section, depth: 6 })).toBe('h4');
	});
});
