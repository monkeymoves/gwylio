/**
 * The method, in plain strings, for the About page and the notes under the
 * coverage tables. Edit the words here; the components only lay them out.
 *
 * The grading scales and the lifecycle states repeat the wording of
 * `enums.json` and `docs/RUBRIC.md`; a Vitest test checks the labels still
 * agree with the published enums, so a change in one place is caught.
 * No en or em dashes: use commas, colons or "to".
 */

export interface AboutTable {
	caption: string;
	headers: string[];
	rows: string[][];
}

export interface AboutListItem {
	/** A bold lead-in, such as the bias guard's name. */
	term?: string;
	text: string;
}

export interface AboutSection {
	id: string;
	heading: string;
	paragraphs: string[];
	list?: { ordered: boolean; items: AboutListItem[] };
	tables?: AboutTable[];
	/** Paragraphs after the list and tables. */
	after?: string[];
}

export interface AboutContent {
	title: string;
	lead: string[];
	sections: AboutSection[];
}

/** Reliability letters with their Admiralty label and the rubric's anchor. */
export const RELIABILITY_SCALE: readonly [string, string, string][] = [
	[
		'A',
		'completely reliable',
		'The authoritative publisher of the record itself, such as legislation.gov.uk for an Act.'
	],
	[
		'B',
		'usually reliable',
		'Government, regulators, the Senedd, audit and statutory bodies speaking about their own decisions.'
	],
	[
		'C',
		'fairly reliable',
		'Established charities, unions, think tanks, research councils and news outlets with an editorial process.'
	],
	[
		'D',
		'not usually reliable',
		'Campaign groups and parties to a dispute: often right, always arguing a case.'
	],
	['E', 'unreliable', 'A source with a record of getting this kind of thing wrong.'],
	['F', 'cannot be judged', 'A source new to the watchlist, or one with no track record yet.']
];

/** Credibility digits with their Admiralty label and the rubric's anchor. */
export const CREDIBILITY_SCALE: readonly [string, string, string][] = [
	[
		'1',
		'confirmed',
		'Settled fact confirmed by the primary record: the Act has Royal Assent, the figures are published.'
	],
	[
		'2',
		'probably true',
		'The publisher reports its own decision or data, consistent with what else we know.'
	],
	[
		'3',
		'possibly true',
		'Reported second hand, or a proposal, consultation or forecast whose outcome is open.'
	],
	[
		'4',
		'doubtful',
		'One claim against the weight of other evidence, or a report that hedges heavily.'
	],
	[
		'5',
		'improbable',
		'Contradicted by better evidence; recorded only if the claim itself matters.'
	],
	['6', 'cannot be judged', 'Nothing to test it against yet.']
];

/** The indicator states, in lifecycle order, with how a report reaches each one. */
export const LIFECYCLE_STATES: readonly [string, string][] = [
	['emerging', 'New to the register, seen in one run only.'],
	['tracking', 'Seen again in a scan run that started strictly after the one that found it.'],
	[
		'reinforced',
		'Seen by three distinct sources, or independently confirmed by the analyst. Several sightings from one source in one run are index echo and count once.'
	],
	['matured', 'Settled context, set by the analyst: the Act passed, the fund launched.'],
	[
		'faded',
		'Not seen in the two most recent complete runs, set only by the sweep; a later sighting revives it to tracking.'
	],
	['parked', 'Set aside by the analyst on reflection, and kept for memory.']
];

export const ABOUT: AboutContent = {
	title: 'About Gwylio: the method',
	lead: [
		'Gwylio (Welsh: to watch, to keep watch) is an open-source intelligence (OSINT) system for the Welsh environment. It watches public sources for developments that bear on a set of requirements, keeps the ones that matter as graded intelligence reports, and publishes them as this site and as written products.',
		'The Natural Resources Wales (NRW) corporate plan performance framework is the first requirement set it carries. Each of its strategic indicators is one priority intelligence requirement (PIR): a question the register exists to answer.'
	],
	sections: [
		{
			id: 'cycle',
			heading: 'The intelligence cycle',
			paragraphs: [
				'Direction sets what to look for: the requirement sets, the taxonomy and the watchlist of sources. Collection runs the scan. Processing hands the candidates to an analyst and takes back a judged submission. The register holds the intelligence reports. Dissemination renders the monthly intelligence summary (INTSUM) and the annual strategic assessment. Evaluation, the Sources, Scans and Coverage pages of this site, asks whether the machinery is finding what it should.',
				'This site is a static snapshot of the register, rebuilt each time the snapshot is published. It changes nothing; everything on it is read from published files.'
			]
		},
		{
			id: 'collect-then-judge',
			heading: 'Collect, then judge',
			paragraphs: [
				'The collector and the analyst never do each other\'s job. A scan run gathers hits from web search, site search, feeds and academic indexes, drops what fails the gates (the organisation\'s own domains, negative terms, hits unrelated to Wales), merges hits that share a canonical address, and writes every surviving candidate to a file. It never scores, tags or grades anything.',
				'An analyst, working in a Claude Code skill against a written rubric, opens each candidate, decides its fate and writes a submission: promoted, rejected, duplicate, deferred or reinforcement, with a reason. Ingest validates the whole submission against the rubric\'s rules and applies it all or nothing. Every candidate keeps its fate, so the yield of each source and each run can be measured.'
			]
		},
		{
			id: 'grading',
			heading: 'Admiralty grading',
			paragraphs: [
				'Every report carries a grading such as B2: a letter for the source and a digit for the information. They are judged separately on purpose. A reliable source can publish a forecast that is only possibly true; a campaign group can report its own court win, which is easily checked.',
				'The letter belongs to the source and is fixed on the watchlist; a submission cannot change it. The digit is the analyst\'s judgement of one report, made from the page itself.'
			],
			tables: [
				{
					caption: 'Source reliability, A to F',
					headers: ['Letter', 'Label', 'Anchor'],
					rows: RELIABILITY_SCALE.map((row) => [...row])
				},
				{
					caption: 'Information credibility, 1 to 6',
					headers: ['Digit', 'Label', 'Anchor'],
					rows: CREDIBILITY_SCALE.map((row) => [...row])
				}
			],
			after: [
				'Grades inflate quietly. If most of a run\'s promotions are 1 or 2, look again: a consultation is a 3, however official the page. The Scans page shows the credibility spread of each run\'s promotions so the drift is visible.'
			]
		},
		{
			id: 'lifecycle',
			heading: 'The lifecycle of a report',
			paragraphs: [
				'A report\'s state is an indications and warnings lifecycle, derived from its sightings across scan runs and counted as distinct runs and distinct sources, never raw hits. The analyst sets only matured and parked. Nothing is ever deleted: every change appends a dated entry to the report\'s history.'
			],
			tables: [
				{
					caption: 'Indicator states',
					headers: ['State', 'How a report gets there'],
					rows: LIFECYCLE_STATES.map((row) => [...row])
				}
			]
		},
		{
			id: 'bias-guards',
			heading: 'Three bias guards',
			paragraphs: [
				'The analyst asks three questions before closing a pass, and answers them in the method note of each product.'
			],
			list: {
				ordered: true,
				items: [
					{
						term: 'Optimism.',
						text: 'What in this pool threatens a requirement, cuts funding, weakens a regime or could go either way? Government sources announce what they are doing, so a scan of them surfaces support. A register where everything supports everything is a symptom, not a finding.'
					},
					{
						term: 'Mainstream.',
						text: 'What did we promote that is not government, a regulator or NRW itself? The earliest signals often arrive as litigation, petitions, campaigns, market moves and independent reporting.'
					},
					{
						term: 'Streetlight.',
						text: 'What could move a requirement that this instrument would never find? The scan only finds what already talks like the requirements. A gap you can name is a probe to run; a gap you cannot see is a blind spot to declare.'
					}
				]
			}
		},
		{
			id: 'horizons',
			heading: 'Two horizons',
			paragraphs: [
				'Gwylio is the near-field horizon: monitoring anchored on the requirements, verified to source, and kept as a trend line in the register. By design it finds what already talks like the requirements. Ecological early warnings (tree and plant disease, invasive species, avian influenza, drought) are scanned on purpose to stretch that reach.',
				'The far-field horizon of surprise, discontinuity and wildcards is a separate foresight exercise. It is kept out of the register on purpose, so speculation never dilutes the verified trend line, and it shares only the requirement sets with this system.'
			]
		},
		{
			id: 'blind-spot',
			heading: 'A blind spot is not quiet',
			paragraphs: [
				'Every requirement carries a scanability: how far public, indexed sources can see it at all, from high to none. A requirement with no active reports reads quiet when public sources could see movement if there were any, and blind spot when they cannot.',
				'A quiet requirement is reported as quiet, in a sentence. A blind spot is never reported as quiet: its silence is not evidence of anything, because its evidence is internal to the organisation or arrives only in known release windows. The site shows a blind spot with an inverse, hatched chip that reads "blind spot: not scannable", never with the outline used for quiet.',
				'Counts of reports are not counts of impact. The register shows what surfaced publicly: at least this much, and known to undercount.'
			]
		}
	]
};

/** One sentence under each coverage table saying what its axis is. */
export const COVERAGE_NOTES = {
	lanes:
		'Each row is a requirement and each column a lane, the part of the public record a source sits in; a cell counts the active reports on the requirement found in that lane, and the row status comes from the requirement\'s scanability and total, so one public sources cannot see reads blind spot, never quiet.',
	taxonomy:
		'Each row is a node of this taxonomy axis; the count is the active reports whose requirements expect the node or whose hazards belong to it, and a node no requirement expects and no report touches is a blind spot of the framework, not a quiet one.',
	credibility:
		'Active reports assessed against this set, by the credibility digit the analyst gave each one: a register heavy in 1 and 2 deserves a second look.'
} as const;
