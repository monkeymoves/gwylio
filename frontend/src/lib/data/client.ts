/**
 * Typed loaders over the published snapshot (or, in development, the read API).
 *
 * The built site reads the JSON snapshot that `gwylio publish` writes into
 * `static/data/`, served at `/data`. Setting `PUBLIC_GWYLIO_API_BASE` (see
 * `.env.example`) at build or dev time switches every loader to the read API,
 * such as `http://localhost:8000/api/v1`. Both serve the same documents, so
 * the types are the same either way.
 *
 * Every loader takes the `fetch` it should use: pass SvelteKit's load `fetch`
 * so prerendering inlines the response into the page.
 */
import type {
	Coverage,
	DateCheck,
	Enums,
	Meta,
	Picture,
	ProductDetail,
	ProductSummary,
	ReportDetail,
	ReportSummary,
	RequirementSetDetail,
	RequirementSetSummary,
	RunDetail,
	RunSummary,
	SourceSummary,
	SourcesHealth
} from './types.generated';

/** The fetch a loader uses; SvelteKit's load fetch or the global one. */
export type Fetch = typeof globalThis.fetch;

/** Where the published snapshot is served from in the static site. */
export const SNAPSHOT_BASE = '/data';

/** Which shape of paths the base serves. */
export type DataMode = 'snapshot' | 'api';

export interface DataSource {
	mode: DataMode;
	/** The base URL with no trailing slash. */
	base: string;
}

/** Every document the site can load. */
export type Resource =
	| { kind: 'meta' }
	| { kind: 'enums' }
	| { kind: 'requirementSets' }
	| { kind: 'requirementSet'; id: string }
	| { kind: 'picture'; id: string }
	| { kind: 'coverage'; id: string }
	| { kind: 'reports' }
	| { kind: 'report'; id: string }
	| { kind: 'sources' }
	| { kind: 'sourcesHealth' }
	| { kind: 'runs' }
	| { kind: 'run'; id: string }
	| { kind: 'datecheck' }
	| { kind: 'products' }
	| { kind: 'product'; id: string };

/**
 * The data source for an API base: the snapshot when the base is empty or
 * unset, the read API otherwise.
 */
export function dataSource(apiBase: string | undefined = configuredApiBase()): DataSource {
	const trimmed = (apiBase ?? '').trim().replace(/\/+$/, '');
	return trimmed ? { mode: 'api', base: trimmed } : { mode: 'snapshot', base: SNAPSHOT_BASE };
}

function configuredApiBase(): string | undefined {
	return import.meta.env.PUBLIC_GWYLIO_API_BASE;
}

const id = encodeURIComponent;

/** The URL of one document under a data source. Pure, so it is tested directly. */
export function resourceUrl(source: DataSource, resource: Resource): string {
	const path = source.mode === 'api' ? apiPath(resource) : snapshotPath(resource);
	return `${source.base}/${path}`;
}

function snapshotPath(r: Resource): string {
	switch (r.kind) {
		case 'meta':
			return 'meta.json';
		case 'enums':
			return 'enums.json';
		case 'requirementSets':
			return 'requirement_sets.json';
		case 'requirementSet':
			return `requirement_set_${id(r.id)}.json`;
		case 'picture':
			return `picture_${id(r.id)}.json`;
		case 'coverage':
			return `coverage_${id(r.id)}.json`;
		case 'reports':
			return 'reports.json';
		case 'report':
			return `reports/${id(r.id)}.json`;
		case 'sources':
			return 'sources.json';
		case 'sourcesHealth':
			return 'sources_health.json';
		case 'runs':
			return 'runs.json';
		case 'run':
			return `runs/${id(r.id)}.json`;
		case 'datecheck':
			return 'datecheck.json';
		case 'products':
			return 'products.json';
		case 'product':
			return `products/${id(r.id)}.json`;
	}
}

function apiPath(r: Resource): string {
	switch (r.kind) {
		case 'meta':
			return 'meta';
		case 'enums':
			return 'meta/enums';
		case 'requirementSets':
			return 'requirement-sets';
		case 'requirementSet':
			return `requirement-sets/${id(r.id)}`;
		case 'picture':
			return `requirement-sets/${id(r.id)}/picture`;
		case 'coverage':
			return `coverage/${id(r.id)}`;
		case 'reports':
			return 'reports';
		case 'report':
			return `reports/${id(r.id)}`;
		case 'sources':
			return 'sources';
		case 'sourcesHealth':
			return 'sources/health';
		case 'runs':
			return 'scan-runs';
		case 'run':
			return `scan-runs/${id(r.id)}`;
		case 'datecheck':
			return 'datecheck';
		case 'products':
			return 'products';
		case 'product':
			return `products/${id(r.id)}`;
	}
}

/** A document could not be loaded; `status` is the HTTP status, 0 for a network failure. */
export class DataError extends Error {
	readonly status: number;
	readonly url: string;

	constructor(message: string, status: number, url: string) {
		super(message);
		this.name = 'DataError';
		this.status = status;
		this.url = url;
	}
}

/** Fetch and parse one document. Throws `DataError` on a failed response. */
export async function loadResource<T>(
	resource: Resource,
	fetchFn: Fetch = globalThis.fetch,
	source: DataSource = dataSource()
): Promise<T> {
	const url = resourceUrl(source, resource);
	let response: Response;
	try {
		response = await fetchFn(url, { headers: { accept: 'application/json' } });
	} catch (cause) {
		throw new DataError(`Could not reach ${url}: ${String(cause)}`, 0, url);
	}
	if (!response.ok) {
		throw new DataError(`${url} answered ${response.status}`, response.status, url);
	}
	return (await response.json()) as T;
}

export const loadMeta = (f?: Fetch, s?: DataSource) => loadResource<Meta>({ kind: 'meta' }, f, s);

export const loadEnums = (f?: Fetch, s?: DataSource) =>
	loadResource<Enums>({ kind: 'enums' }, f, s);

export const loadRequirementSets = (f?: Fetch, s?: DataSource) =>
	loadResource<RequirementSetSummary[]>({ kind: 'requirementSets' }, f, s);

export const loadRequirementSet = (setId: string, f?: Fetch, s?: DataSource) =>
	loadResource<RequirementSetDetail>({ kind: 'requirementSet', id: setId }, f, s);

export const loadPicture = (setId: string, f?: Fetch, s?: DataSource) =>
	loadResource<Picture>({ kind: 'picture', id: setId }, f, s);

export const loadCoverage = (setId: string, f?: Fetch, s?: DataSource) =>
	loadResource<Coverage>({ kind: 'coverage', id: setId }, f, s);

/** Every report summary, unfiltered: the list page filters client-side. */
export const loadReports = (f?: Fetch, s?: DataSource) =>
	loadResource<ReportSummary[]>({ kind: 'reports' }, f, s);

export const loadReport = (reportId: string, f?: Fetch, s?: DataSource) =>
	loadResource<ReportDetail>({ kind: 'report', id: reportId }, f, s);

export const loadSources = (f?: Fetch, s?: DataSource) =>
	loadResource<SourceSummary[]>({ kind: 'sources' }, f, s);

export const loadSourcesHealth = (f?: Fetch, s?: DataSource) =>
	loadResource<SourcesHealth>({ kind: 'sourcesHealth' }, f, s);

export const loadRuns = (f?: Fetch, s?: DataSource) =>
	loadResource<RunSummary[]>({ kind: 'runs' }, f, s);

export const loadRun = (runId: string, f?: Fetch, s?: DataSource) =>
	loadResource<RunDetail>({ kind: 'run', id: runId }, f, s);

export const loadDateCheck = (f?: Fetch, s?: DataSource) =>
	loadResource<DateCheck>({ kind: 'datecheck' }, f, s);

export const loadProducts = (f?: Fetch, s?: DataSource) =>
	loadResource<ProductSummary[]>({ kind: 'products' }, f, s);

export const loadProduct = (productId: string, f?: Fetch, s?: DataSource) =>
	loadResource<ProductDetail>({ kind: 'product', id: productId }, f, s);
