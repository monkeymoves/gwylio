import { error } from '@sveltejs/kit';
import { productSummaries, readSnapshot } from '$lib/server/snapshot';
import type { ProductDetail } from '$lib/data/types.generated';
import type { EntryGenerator, RequestHandler } from './$types';

/**
 * Each product's Markdown as a static file beside the site, such as
 * /products/operational_2026-10.md, so the INTSUM page can link to it on
 * static hosting. The text is the `body` of the product in the snapshot.
 */
export const prerender = true;

export const entries: EntryGenerator = () =>
	productSummaries().map((product) => ({ file: product.markdown_file }));

export const GET: RequestHandler = ({ params }) => {
	const summary = productSummaries().find((product) => product.markdown_file === params.file);
	if (!summary) error(404, `No product Markdown called ${params.file}`);
	const detail = readSnapshot<ProductDetail>(`products/${summary.id}.json`);
	return new Response(detail.body, {
		headers: { 'content-type': 'text/markdown; charset=utf-8' }
	});
};
