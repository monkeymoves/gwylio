import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { enums, seed } from '../../../tests/fixtures';
import type { Picture } from '$lib/data/types.generated';
import RequirementTile from './RequirementTile.svelte';

// The seed picture: SI1 is covered and SI12 a blind spot whatever the live register holds.
const picture = seed<Picture>('picture.json');

function tile(id: string) {
	const found = picture.requirements.find((r) => r.requirement_id === id);
	if (!found) throw new Error(`no tile ${id}`);
	return found;
}

describe('RequirementTile', () => {
	it('links to the filtered report list and shows code, short name, bar and dates', () => {
		const si1 = tile('si1');
		const { container } = render(RequirementTile, {
			tile: si1,
			enums,
			href: '/reports?requirement=si1'
		});
		const link = screen.getByRole('link');
		expect(link).toHaveAttribute('href', '/reports?requirement=si1');
		expect(link).toHaveTextContent(si1.code);
		expect(link).toHaveTextContent(si1.short);
		expect(screen.getByRole('img')).toHaveAttribute('aria-label', expect.stringContaining('threatens'));
		expect(container.querySelector('[data-status="covered"]')).toBeInTheDocument();
		expect(screen.getByText('Latest horizon')).toBeInTheDocument();
	});

	it('shows a blind spot with its note in place of a bar, never as quiet', () => {
		const { container } = render(RequirementTile, {
			tile: tile('si12'),
			enums,
			href: '/reports?requirement=si12',
			scanabilityNote: 'Internal staff survey.'
		});
		expect(screen.getByText('blind spot: not scannable')).toBeInTheDocument();
		expect(screen.getByText('Internal staff survey.')).toBeInTheDocument();
		expect(container.querySelector('.direction-bar')).not.toBeInTheDocument();
		expect(container.querySelector('[data-status="quiet"]')).not.toBeInTheDocument();
		expect(screen.getByRole('link')).toHaveClass('blind');
	});
});
