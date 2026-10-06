import { describe, expect, it } from 'vitest';
import {
	DataError,
	SNAPSHOT_BASE,
	dataSource,
	loadPicture,
	loadReport,
	loadResource,
	resourceUrl,
	type Fetch,
	type Resource
} from './client';

const snapshot = dataSource('');
const api = dataSource('http://localhost:8000/api/v1/');

describe('dataSource', () => {
	it('reads the snapshot when no API base is set', () => {
		expect(dataSource(undefined)).toEqual({ mode: 'snapshot', base: SNAPSHOT_BASE });
		expect(dataSource('   ')).toEqual({ mode: 'snapshot', base: '/data' });
	});

	it('switches to the API and drops trailing slashes', () => {
		expect(api).toEqual({ mode: 'api', base: 'http://localhost:8000/api/v1' });
	});
});

describe('resourceUrl', () => {
	const cases: Array<[Resource, string, string]> = [
		[{ kind: 'meta' }, '/data/meta.json', '/meta'],
		[{ kind: 'enums' }, '/data/enums.json', '/meta/enums'],
		[{ kind: 'requirementSets' }, '/data/requirement_sets.json', '/requirement-sets'],
		[{ kind: 'requirementSet', id: 'nrw' }, '/data/requirement_set_nrw.json', '/requirement-sets/nrw'],
		[{ kind: 'picture', id: 'nrw' }, '/data/picture_nrw.json', '/requirement-sets/nrw/picture'],
		[{ kind: 'coverage', id: 'nrw' }, '/data/coverage_nrw.json', '/coverage/nrw'],
		[{ kind: 'reports' }, '/data/reports.json', '/reports'],
		[{ kind: 'report', id: 'r-1' }, '/data/reports/r-1.json', '/reports/r-1'],
		[{ kind: 'sources' }, '/data/sources.json', '/sources'],
		[{ kind: 'sourcesHealth' }, '/data/sources_health.json', '/sources/health'],
		[{ kind: 'runs' }, '/data/runs.json', '/scan-runs'],
		[{ kind: 'run', id: 'run-1' }, '/data/runs/run-1.json', '/scan-runs/run-1'],
		[{ kind: 'datecheck' }, '/data/datecheck.json', '/datecheck'],
		[{ kind: 'products' }, '/data/products.json', '/products'],
		[{ kind: 'product', id: 'p-1' }, '/data/products/p-1.json', '/products/p-1']
	];

	it.each(cases)('%o', (resource, snapshotUrl, apiPath) => {
		expect(resourceUrl(snapshot, resource)).toBe(snapshotUrl);
		expect(resourceUrl(api, resource)).toBe(`http://localhost:8000/api/v1${apiPath}`);
	});

	it('encodes ids', () => {
		expect(resourceUrl(snapshot, { kind: 'report', id: 'a/b c' })).toBe('/data/reports/a%2Fb%20c.json');
	});
});

describe('loadResource', () => {
	function fakeFetch(status: number, body: unknown, seen: string[] = []): Fetch {
		return (async (input: RequestInfo | URL) => {
			seen.push(String(input));
			return new Response(JSON.stringify(body), { status });
		}) as Fetch;
	}

	it('fetches the URL for the resource and parses the JSON', async () => {
		const seen: string[] = [];
		const picture = await loadPicture('nrw', fakeFetch(200, { set_id: 'nrw' }, seen), snapshot);
		expect(picture.set_id).toBe('nrw');
		expect(seen).toEqual(['/data/picture_nrw.json']);
	});

	it('throws a DataError carrying the status on a failed response', async () => {
		const failure = loadReport('missing', fakeFetch(404, { detail: 'not found' }), api);
		await expect(failure).rejects.toBeInstanceOf(DataError);
		await expect(failure).rejects.toMatchObject({
			status: 404,
			url: 'http://localhost:8000/api/v1/reports/missing'
		});
	});

	it('throws a DataError with status 0 when the network fails', async () => {
		const offline = (async () => {
			throw new TypeError('offline');
		}) as Fetch;
		await expect(loadResource({ kind: 'meta' }, offline, snapshot)).rejects.toMatchObject({
			status: 0
		});
	});
});
