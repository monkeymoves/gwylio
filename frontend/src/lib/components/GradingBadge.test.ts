import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import GradingBadge, { gradingTitle } from './GradingBadge.svelte';

const props = {
	reliability: 'B' as const,
	credibility: 2 as const,
	reliabilityLabel: 'usually reliable',
	credibilityLabel: 'probably true'
};

describe('GradingBadge', () => {
	it('shows the grading and spells out both labels in its title', () => {
		render(GradingBadge, props);
		const badge = screen.getByText('B2');
		expect(badge).toHaveAttribute(
			'title',
			'Source reliability B: usually reliable. Information credibility 2: probably true.'
		);
		expect(screen.queryByText('usually reliable')).not.toBeInTheDocument();
	});

	it('shows both labels beside the badge when asked', () => {
		render(GradingBadge, { ...props, showLabels: true });
		expect(screen.getByText('usually reliable')).toBeInTheDocument();
		expect(screen.getByText('probably true')).toBeInTheDocument();
	});

	it('builds the title from the props alone', () => {
		expect(gradingTitle({ ...props, reliability: 'F', credibility: 6, reliabilityLabel: 'cannot be judged', credibilityLabel: 'cannot be judged' })).toBe(
			'Source reliability F: cannot be judged. Information credibility 6: cannot be judged.'
		);
	});
});
