import { error } from '@sveltejs/kit';
import { DataError, loadEnums, loadProduct, loadProducts } from '$lib/data/client';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch, params }) => {
	try {
		const [products, product, enums] = await Promise.all([
			loadProducts(fetch),
			loadProduct(params.id, fetch),
			loadEnums(fetch)
		]);
		return { products, product, enums };
	} catch (cause) {
		if (cause instanceof DataError && cause.status === 404) {
			error(404, `No product called ${params.id}`);
		}
		throw cause;
	}
};
