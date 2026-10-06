import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import CoverageChip, { BLIND_SPOT_TEXT, coverageText } from './CoverageChip.svelte';

describe('CoverageChip', () => {
	it('reads "blind spot: not scannable" with its own class, whatever label it is given', () => {
		const { container } = render(CoverageChip, { status: 'blind_spot', label: 'blind spot' });
		expect(screen.getByText(BLIND_SPOT_TEXT)).toBeInTheDocument();
		const chip = container.querySelector('[data-status="blind_spot"]');
		expect(chip).toHaveClass('status-blind-spot');
		expect(chip).not.toHaveClass('status-quiet');
	});

	it('styles quiet differently from a blind spot', () => {
		const { container } = render(CoverageChip, { status: 'quiet', label: 'quiet' });
		const chip = container.querySelector('[data-status="quiet"]');
		expect(chip).toHaveClass('status-quiet');
		expect(chip).not.toHaveClass('status-blind-spot');
		expect(screen.getByText('quiet')).toBeInTheDocument();
		expect(screen.queryByText(BLIND_SPOT_TEXT)).not.toBeInTheDocument();
	});

	it('shows a count and the meaning as its title', () => {
		const { container } = render(CoverageChip, {
			status: 'covered',
			label: 'covered',
			count: 3,
			meaning: 'Three or more active reports.'
		});
		expect(container.querySelector('.count')).toHaveTextContent('3');
		expect(container.querySelector('.chip')).toHaveAttribute('title', 'Three or more active reports.');
	});

	it('maps every status to text', () => {
		expect(coverageText('thin', 'thin')).toBe('thin');
		expect(coverageText('covered')).toBe('covered');
		expect(coverageText('blind_spot', 'anything')).toBe(BLIND_SPOT_TEXT);
	});
});
