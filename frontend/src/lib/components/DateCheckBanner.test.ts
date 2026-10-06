import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import { enums } from '../../../tests/fixtures';
import DateCheckBanner from './DateCheckBanner.svelte';

const counts = {
	passed_horizon: 1,
	future_language: 3,
	stale_verification: 35,
	never_verified: 0,
	total: 39,
	reports_flagged: 35
};

describe('DateCheckBanner', () => {
	it('counts findings by kind with the enum labels and links to the queue', () => {
		render(DateCheckBanner, { counts, enums });
		expect(screen.getByRole('heading')).toHaveTextContent('Date check: 39 findings on 35 reports');
		expect(screen.getByText('Passed event horizons')).toBeInTheDocument();
		expect(screen.getByText('Never verified').closest('li')).toHaveClass('zero');
		expect(screen.getByRole('link')).toHaveAttribute('href', '/verify');
	});

	it('renders nothing when the date check is clean', () => {
		const { container } = render(DateCheckBanner, {
			counts: { ...counts, passed_horizon: 0, future_language: 0, stale_verification: 0, total: 0, reports_flagged: 0 },
			enums
		});
		expect(container.querySelector('aside')).not.toBeInTheDocument();
	});
});
