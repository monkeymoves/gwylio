import { error } from '@sveltejs/kit';
import { DataError, loadEnums, loadRun } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	try {
		const [run, enums] = await Promise.all([loadRun(params.id, fetch), loadEnums(fetch)]);
		return { run, enums };
	} catch (cause) {
		if (cause instanceof DataError && cause.status === 404) {
			error(404, `No scan run called ${params.id}`);
		}
		throw cause;
	}
};
