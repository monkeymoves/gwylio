import { loadDateCheck, loadEnums } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [datecheck, enums] = await Promise.all([loadDateCheck(fetch), loadEnums(fetch)]);
	return { datecheck, enums };
};
