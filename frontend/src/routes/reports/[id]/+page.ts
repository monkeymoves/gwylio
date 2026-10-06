import { error } from '@sveltejs/kit';
import { DataError, loadEnums, loadReport } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	try {
		const [report, enums] = await Promise.all([loadReport(params.id, fetch), loadEnums(fetch)]);
		return { report, enums };
	} catch (cause) {
		if (cause instanceof DataError && cause.status === 404) {
			error(404, `No report called ${params.id}`);
		}
		throw cause;
	}
};
