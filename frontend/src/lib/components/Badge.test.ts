import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import Badge from './Badge.svelte';

describe('Badge', () => {
	it('renders its label with the neutral tone by default', () => {
		render(Badge, { label: 'B2' });
		const badge = screen.getByText('B2');
		expect(badge).toBeInTheDocument();
		expect(badge).toHaveAttribute('data-tone', 'neutral');
	});

	it('carries the requested tone', () => {
		render(Badge, { label: 'blind spot', tone: 'warn' });
		expect(screen.getByText('blind spot')).toHaveAttribute('data-tone', 'warn');
	});
});
