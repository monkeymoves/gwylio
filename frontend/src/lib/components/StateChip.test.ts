import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import StateChip from './StateChip.svelte';

describe('StateChip', () => {
	it('shows the label, the count and the meaning', () => {
		const { container } = render(StateChip, {
			state: 'emerging',
			label: 'emerging',
			count: 12,
			meaning: 'New to the register, seen in one run only.'
		});
		expect(screen.getByText('emerging')).toBeInTheDocument();
		expect(container.querySelector('.count')).toHaveTextContent('12');
		expect(container.querySelector('[data-state="emerging"]')).toHaveAttribute(
			'title',
			'New to the register, seen in one run only.'
		);
	});

	it('falls back to the state value', () => {
		render(StateChip, { state: 'parked' });
		expect(screen.getByText('parked')).toBeInTheDocument();
	});
});
