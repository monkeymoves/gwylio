import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { beforeEach, describe, expect, it } from 'vitest';
import { GATE_STORAGE_KEY } from '$lib/gate';
import PasswordGate from './PasswordGate.svelte';

const OPEN_SESAME = '6503a68a8cd729564b34ef8efa32fc23203ddd24fbca79613df9bbc67996d8c1';
const site = createRawSnippet(() => ({ render: () => '<p>The register</p>' }));

describe('PasswordGate', () => {
	beforeEach(() => localStorage.clear());

	it('shows the site straight away when no hash is configured', () => {
		render(PasswordGate, { hash: null, children: site });
		expect(screen.getByText('The register')).toBeInTheDocument();
		expect(screen.queryByLabelText('Password')).not.toBeInTheDocument();
	});

	it('hides the site behind the screen and refuses a wrong password', async () => {
		render(PasswordGate, { hash: OPEN_SESAME, children: site });
		expect(screen.queryByText('The register')).not.toBeInTheDocument();
		await fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'wrong' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
		expect(await screen.findByRole('alert')).toHaveTextContent('That password is not right');
		expect(screen.queryByText('The register')).not.toBeInTheDocument();
		expect(localStorage.getItem(GATE_STORAGE_KEY)).toBeNull();
	});

	it('opens on the right password and remembers it', async () => {
		render(PasswordGate, { hash: OPEN_SESAME, children: site });
		await fireEvent.input(screen.getByLabelText('Password'), { target: { value: 'open sesame' } });
		await fireEvent.click(screen.getByRole('button', { name: 'Enter' }));
		expect(await screen.findByText('The register')).toBeInTheDocument();
		expect(localStorage.getItem(GATE_STORAGE_KEY)).toBe(OPEN_SESAME);
	});

	it('skips the screen for a browser that unlocked before', async () => {
		localStorage.setItem(GATE_STORAGE_KEY, OPEN_SESAME);
		render(PasswordGate, { hash: OPEN_SESAME, children: site });
		await waitFor(() => expect(screen.getByText('The register')).toBeInTheDocument());
	});
});
