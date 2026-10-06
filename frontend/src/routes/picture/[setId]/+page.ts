import { error } from '@sveltejs/kit';
import {
	DataError,
	loadEnums,
	loadPicture,
	loadRequirementSet
} from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	try {
		const [picture, set, enums] = await Promise.all([
			loadPicture(params.setId, fetch),
			loadRequirementSet(params.setId, fetch),
			loadEnums(fetch)
		]);
		return { picture, set, enums };
	} catch (cause) {
		if (cause instanceof DataError && cause.status === 404) {
			error(404, `No requirement set called ${params.setId}`);
		}
		throw cause;
	}
};
