import { loadEnums, loadReports, loadRequirementSet } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, data, parent }) => {
	const { meta } = await parent();
	const [reports, enums, sets] = await Promise.all([
		loadReports(fetch),
		loadEnums(fetch),
		Promise.all(meta.requirement_set_ids.map((setId) => loadRequirementSet(setId, fetch)))
	]);
	return { ...data, reports, enums, sets };
};
