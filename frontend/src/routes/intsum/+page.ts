import { loadEnums, loadProduct, loadProducts } from '$lib/data/client';
import { defaultProduct } from '$lib/data/products';
import type { PageLoad } from './$types';

/** The latest operational product (INTSUM), or the latest of any level, with the list for the selector. */
export const load: PageLoad = async ({ fetch }) => {
	const [products, enums] = await Promise.all([loadProducts(fetch), loadEnums(fetch)]);
	const chosen = defaultProduct(products);
	const product = chosen ? await loadProduct(chosen.id, fetch) : null;
	return { products, product, enums };
};
