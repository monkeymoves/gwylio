/**
 * Build-time reads of the published snapshot in `static/data/`.
 *
 * Used only by server files (`+page.server.ts`, `+server.ts`) while prerendering: to declare the
 * `entries` of dynamic routes, so every report, requirement set, scan run and
 * product page (and each product's Markdown) exists
 * as a static file, and to build the topic, hazard and place names the report
 * filters show (`reports.json` carries ids only). Browsers never run this; at
 * runtime the client fetches `/data/*.json` through `$lib/data/client`.
 */
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import type {
	Meta,
	ProductSummary,
	ReportDetail,
	ReportSummary,
	RunSummary
} from '$lib/data/types.generated';

function snapshotDir(): string {
	const candidates = [
		path.resolve(process.cwd(), 'static', 'data'),
		path.resolve(process.cwd(), 'frontend', 'static', 'data')
	];
	const found = candidates.find((dir) => existsSync(path.join(dir, 'meta.json')));
	if (!found) {
		throw new Error(`No published snapshot found; looked in ${candidates.join(' and ')}`);
	}
	return found;
}

/** Parse one snapshot file, by its path under `static/data/`. */
export function readSnapshot<T>(relative: string): T {
	return JSON.parse(readFileSync(path.join(snapshotDir(), relative), 'utf8')) as T;
}

/** The requirement set ids the snapshot publishes a picture for. */
export function requirementSetIds(): string[] {
	return readSnapshot<Meta>('meta.json').requirement_set_ids;
}

/** Every report id in the snapshot. */
export function reportIds(): string[] {
	return readSnapshot<ReportSummary[]>('reports.json').map((report) => report.id);
}

/** Catalogue names by id for the tags the reports carry. */
export interface TagNames {
	topics: Record<string, string>;
	hazards: Record<string, string>;
	places: Record<string, string>;
}

/** The names of every topic, hazard and place used by a report, from the report details. */
export function tagNames(): TagNames {
	const names: TagNames = { topics: {}, hazards: {}, places: {} };
	for (const id of reportIds()) {
		const detail = readSnapshot<ReportDetail>(`reports/${id}.json`);
		for (const topic of detail.topics) names.topics[topic.id] = topic.name;
		for (const hazard of detail.hazards) names.hazards[hazard.id] = hazard.name;
		for (const place of detail.places) names.places[place.id] = place.name;
	}
	return names;
}

/** Every scan run id in the snapshot; empty until a run is published. */
export function runIds(): string[] {
	return readSnapshot<RunSummary[]>('runs.json').map((run) => run.run_id);
}

/** Every product summary in the snapshot. */
export function productSummaries(): ProductSummary[] {
	return readSnapshot<ProductSummary[]>('products.json');
}

/** Every product id in the snapshot. */
export function productIds(): string[] {
	return productSummaries().map((product) => product.id);
}
