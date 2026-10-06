import { sveltekit } from '@sveltejs/kit/vite';
import { svelteTesting } from '@testing-library/svelte/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit(), svelteTesting()],
	// PUBLIC_GWYLIO_API_BASE switches the data client to the read API (see .env.example).
	envPrefix: ['VITE_', 'PUBLIC_'],
	test: {
		environment: 'jsdom',
		include: ['src/**/*.{test,spec}.{js,ts}', 'tests/**/*.{test,spec}.{js,ts}'],
		setupFiles: ['./tests/setup.ts']
	}
});
