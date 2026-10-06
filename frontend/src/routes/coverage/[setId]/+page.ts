import { error } from '@sveltejs/kit';
import { DataError, loadCoverage } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	try {
		return { coverage: await loadCoverage(params.setId, fetch) };
	} catch (cause) {
		if (cause instanceof DataError && cause.status === 404) {
			error(404, `No requirement set called ${params.setId}`);
		}
		throw cause;
	}
};
