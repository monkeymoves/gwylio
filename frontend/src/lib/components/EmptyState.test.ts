import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';
import EmptyState from './EmptyState.svelte';

describe('EmptyState', () => {
	it('announces its title and message as a status', () => {
		render(EmptyState, { title: 'No reports match these filters', message: 'Clear a filter.' });
		const status = screen.getByRole('status');
		expect(status).toHaveTextContent('No reports match these filters');
		expect(status).toHaveTextContent('Clear a filter.');
	});
});
