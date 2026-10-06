import { loadEnums, loadRuns } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [runs, enums] = await Promise.all([loadRuns(fetch), loadEnums(fetch)]);
	return { runs, enums };
};
