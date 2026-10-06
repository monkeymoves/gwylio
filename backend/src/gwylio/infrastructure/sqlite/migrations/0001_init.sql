-- Migration 0001: the Reference, Direction and Collection tables.
--
-- The database is a projection of config/ plus the files under data/; every
-- row here can be rebuilt from them (ADR 0002). Conventions:
--   * enum columns are TEXT with a CHECK listing the allowed values, in the
--     order the domain enum declares them (the domain validates too; the
--     CHECK is a second lock);
--   * dates are ISO text, YYYY-MM-DD; timestamps are ISO UTC text,
--     YYYY-MM-DDTHH:MM:SS.ffffffZ;
--   * booleans are INTEGER 0 or 1;
--   * ordered lists of free values (keywords, hints, notes) are JSON arrays
--     of strings; ordered lists that name other rows are child tables with a
--     position and a foreign key;
--   * position columns keep the order the configuration file gives.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL UNIQUE,
    applied_at TEXT NOT NULL
);

-- Reference: taxonomy, lanes and the catalogues.

CREATE TABLE taxonomy_axis (
    id       TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    name     TEXT NOT NULL
);

CREATE TABLE taxonomy_node (
    id       TEXT PRIMARY KEY,
    axis_id  TEXT NOT NULL REFERENCES taxonomy_axis (id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    name     TEXT NOT NULL,
    kind     TEXT NOT NULL CHECK (kind IN ('ecosystem', 'resource', 'hazard_family')),
    note     TEXT,
    UNIQUE (axis_id, position)
);

CREATE TABLE lane (
    id          TEXT PRIMARY KEY,
    position    INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    lens        TEXT NOT NULL CHECK (lens IN ('government', 'partnership_society', 'international')),
    description TEXT NOT NULL
);

CREATE TABLE topic (
    id       TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    name     TEXT NOT NULL,
    note     TEXT
);

CREATE TABLE hazard (
    id       TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    name     TEXT NOT NULL,
    family   TEXT NOT NULL REFERENCES taxonomy_node (id),
    note     TEXT
);

CREATE TABLE place (
    id         TEXT PRIMARY KEY,
    position   INTEGER NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    welsh_name TEXT,
    kind       TEXT NOT NULL
               CHECK (kind IN ('nation', 'region', 'area', 'river_basin', 'settlement', 'site')),
    parent     TEXT REFERENCES place (id),
    latitude   REAL CHECK (latitude BETWEEN -90.0 AND 90.0),
    longitude  REAL CHECK (longitude BETWEEN -180.0 AND 180.0),
    CHECK ((latitude IS NULL) = (longitude IS NULL)),
    CHECK (parent IS NULL OR parent != id)
);

CREATE TABLE actor (
    id       TEXT PRIMARY KEY,
    position INTEGER NOT NULL UNIQUE,
    name     TEXT NOT NULL,
    kind     TEXT NOT NULL CHECK (kind IN ('government', 'legislature', 'regulator', 'public_body', 'research', 'ngo', 'business', 'union', 'media', 'international', 'other')),
    lane     TEXT NOT NULL REFERENCES lane (id),
    domain   TEXT
);

-- Direction: requirement sets, their requirements and groups.

CREATE TABLE requirement_set (
    id         TEXT PRIMARY KEY,
    position   INTEGER NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    version    TEXT NOT NULL,
    source_doc TEXT NOT NULL
);

CREATE TABLE requirement (
    set_id           TEXT NOT NULL REFERENCES requirement_set (id) ON DELETE CASCADE,
    id               TEXT NOT NULL,
    position         INTEGER NOT NULL,
    code             TEXT NOT NULL,
    name             TEXT NOT NULL,
    short            TEXT NOT NULL,
    scanability      TEXT NOT NULL CHECK (scanability IN ('high', 'medium', 'low', 'none')),
    scanability_note TEXT NOT NULL,
    keywords         TEXT NOT NULL CHECK (json_valid(keywords) AND json_type(keywords) = 'array'),
    metric_sources   TEXT NOT NULL
                     CHECK (json_valid(metric_sources) AND json_type(metric_sources) = 'array'),
    development      INTEGER NOT NULL CHECK (development IN (0, 1)),
    PRIMARY KEY (set_id, id),
    UNIQUE (set_id, code),
    UNIQUE (set_id, position)
);

CREATE TABLE requirement_expected_coverage (
    set_id         TEXT NOT NULL,
    requirement_id TEXT NOT NULL,
    position       INTEGER NOT NULL,
    node_id        TEXT NOT NULL REFERENCES taxonomy_node (id),
    PRIMARY KEY (set_id, requirement_id, position),
    FOREIGN KEY (set_id, requirement_id) REFERENCES requirement (set_id, id) ON DELETE CASCADE
);

CREATE TABLE requirement_group (
    set_id    TEXT NOT NULL REFERENCES requirement_set (id) ON DELETE CASCADE,
    id        TEXT NOT NULL,
    position  INTEGER NOT NULL,
    kind      TEXT NOT NULL CHECK (kind IN ('impact', 'wbo')),
    name      TEXT NOT NULL,
    statement TEXT,
    note      TEXT,
    PRIMARY KEY (set_id, id),
    UNIQUE (set_id, position)
);

CREATE TABLE requirement_group_member (
    set_id         TEXT NOT NULL,
    group_id       TEXT NOT NULL,
    position       INTEGER NOT NULL,
    requirement_id TEXT NOT NULL,
    PRIMARY KEY (set_id, group_id, position),
    UNIQUE (set_id, group_id, requirement_id),
    FOREIGN KEY (set_id, group_id) REFERENCES requirement_group (set_id, id) ON DELETE CASCADE,
    FOREIGN KEY (set_id, requirement_id) REFERENCES requirement (set_id, id) ON DELETE CASCADE
);

CREATE TABLE requirement_group_related (
    set_id           TEXT NOT NULL,
    group_id         TEXT NOT NULL,
    position         INTEGER NOT NULL,
    related_group_id TEXT NOT NULL,
    PRIMARY KEY (set_id, group_id, position),
    UNIQUE (set_id, group_id, related_group_id),
    CHECK (related_group_id != group_id),
    FOREIGN KEY (set_id, group_id) REFERENCES requirement_group (set_id, id) ON DELETE CASCADE,
    FOREIGN KEY (set_id, related_group_id) REFERENCES requirement_group (set_id, id)
        ON DELETE CASCADE
);

-- Collection: the watchlist and the query instrument.

CREATE TABLE source (
    id          TEXT PRIMARY KEY,
    position    INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    domain      TEXT NOT NULL UNIQUE,
    feed_url    TEXT,
    discipline  TEXT NOT NULL CHECK (discipline IN ('osint_web', 'osint_feed', 'osint_site', 'osint_academic', 'geoint', 'sensor')),
    lane        TEXT NOT NULL REFERENCES lane (id),
    actor       TEXT NOT NULL REFERENCES actor (id),
    reliability TEXT NOT NULL CHECK (reliability IN ('A', 'B', 'C', 'D', 'E', 'F')),
    trusted     INTEGER NOT NULL CHECK (trusted IN (0, 1)),
    site_pass   INTEGER NOT NULL CHECK (site_pass IN (0, 1)),
    status      TEXT NOT NULL CHECK (status IN ('active', 'parked', 'retired')),
    added_on    TEXT NOT NULL
                CHECK (added_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    notes       TEXT,
    CHECK (discipline != 'osint_feed' OR feed_url IS NOT NULL)
);

-- An instrument version is history: written once, never changed, never
-- deleted by a configuration sync. data/instruments/<version>.json is its fact.
CREATE TABLE instrument_version (
    version               TEXT PRIMARY KEY,
    content_hash          TEXT NOT NULL CHECK (content_hash GLOB 'sha256:*'),
    max_requests_per_run  INTEGER NOT NULL CHECK (max_requests_per_run >= 1),
    global_negative_terms TEXT NOT NULL
        CHECK (json_valid(global_negative_terms) AND json_type(global_negative_terms) = 'array'),
    UNIQUE (version, content_hash)
);

CREATE TABLE instrument_query (
    version           TEXT NOT NULL REFERENCES instrument_version (version) ON DELETE CASCADE,
    position          INTEGER NOT NULL,
    id                TEXT NOT NULL,
    discipline        TEXT NOT NULL CHECK (discipline IN ('osint_web', 'osint_feed', 'osint_site', 'osint_academic', 'geoint', 'sensor')),
    lane              TEXT NOT NULL REFERENCES lane (id),
    text              TEXT NOT NULL,
    requirement_hints TEXT NOT NULL
        CHECK (json_valid(requirement_hints) AND json_type(requirement_hints) = 'array'),
    topic_hints       TEXT NOT NULL
        CHECK (json_valid(topic_hints) AND json_type(topic_hints) = 'array'),
    negative_terms    TEXT NOT NULL
        CHECK (json_valid(negative_terms) AND json_type(negative_terms) = 'array'),
    site_source_ids   TEXT NOT NULL
        CHECK (json_valid(site_source_ids) AND json_type(site_source_ids) = 'array'),
    PRIMARY KEY (version, id),
    UNIQUE (version, position)
);

-- Collection: scan runs and what they found. data/candidates/<run_id>.json is
-- the fact behind every row below.

CREATE TABLE scan_run (
    id                       TEXT PRIMARY KEY
        CHECK (id GLOB '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]T[0-9][0-9][0-9][0-9]Z-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]'),
    started_at               TEXT NOT NULL
        CHECK (started_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'),
    finished_at              TEXT
        CHECK (finished_at GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T[0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9][0-9][0-9][0-9][0-9]Z'),
    status                   TEXT NOT NULL CHECK (status IN ('running', 'complete', 'aborted')),
    instrument_version       TEXT NOT NULL,
    instrument_hash          TEXT NOT NULL,
    request_budget           INTEGER NOT NULL CHECK (request_budget >= 1),
    requests_made            INTEGER NOT NULL CHECK (requests_made >= 0),
    budget_exhausted         INTEGER NOT NULL CHECK (budget_exhausted IN (0, 1)),
    notes                    TEXT NOT NULL CHECK (json_valid(notes) AND json_type(notes) = 'array'),
    funnel_raw               INTEGER NOT NULL CHECK (funnel_raw >= 0),
    funnel_dropped_own       INTEGER NOT NULL CHECK (funnel_dropped_own >= 0),
    funnel_dropped_negative  INTEGER NOT NULL CHECK (funnel_dropped_negative >= 0),
    funnel_dropped_unrelated INTEGER NOT NULL CHECK (funnel_dropped_unrelated >= 0),
    funnel_passed            INTEGER NOT NULL CHECK (funnel_passed >= 0),
    funnel_unique            INTEGER NOT NULL CHECK (funnel_unique >= 0),
    funnel_seen_before       INTEGER NOT NULL CHECK (funnel_seen_before >= 0),
    funnel_new               INTEGER NOT NULL CHECK (funnel_new >= 0),
    funnel_reinforcements    INTEGER NOT NULL CHECK (funnel_reinforcements >= 0),
    -- Runs are stored only once they finish, and then never change.
    CHECK (status != 'running' AND finished_at IS NOT NULL AND finished_at >= started_at),
    FOREIGN KEY (instrument_version, instrument_hash)
        REFERENCES instrument_version (version, content_hash)
);

CREATE INDEX scan_run_started ON scan_run (started_at, id);

CREATE TABLE scan_run_discipline (
    run_id     TEXT NOT NULL REFERENCES scan_run (id) ON DELETE CASCADE,
    position   INTEGER NOT NULL,
    discipline TEXT NOT NULL CHECK (discipline IN ('osint_web', 'osint_feed', 'osint_site', 'osint_academic', 'geoint', 'sensor')),
    PRIMARY KEY (run_id, position),
    UNIQUE (run_id, discipline)
);

CREATE TABLE candidate (
    id                TEXT PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES scan_run (id),
    canonical_url     TEXT NOT NULL,
    url               TEXT NOT NULL,
    title             TEXT NOT NULL,
    snippet           TEXT NOT NULL,
    published_on      TEXT
        CHECK (published_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    first_seen_run_id TEXT NOT NULL REFERENCES scan_run (id),
    trusted           INTEGER NOT NULL CHECK (trusted IN (0, 1)),
    source_id         TEXT REFERENCES source (id),
    lane              TEXT NOT NULL REFERENCES lane (id),
    discipline        TEXT NOT NULL CHECK (discipline IN ('osint_web', 'osint_feed', 'osint_site', 'osint_academic', 'geoint', 'sensor')),
    query_id          TEXT NOT NULL,
    requirement_hints TEXT NOT NULL
        CHECK (json_valid(requirement_hints) AND json_type(requirement_hints) = 'array'),
    topic_hints       TEXT NOT NULL
        CHECK (json_valid(topic_hints) AND json_type(topic_hints) = 'array'),
    -- A canonical URL appears once per run.
    UNIQUE (run_id, canonical_url),
    -- The target of sighting's (candidate_id, run_id) foreign key.
    UNIQUE (id, run_id)
);

CREATE INDEX candidate_canonical_url ON candidate (canonical_url, first_seen_run_id);

CREATE TABLE sighting (
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES scan_run (id),
    candidate_id TEXT NOT NULL REFERENCES candidate (id),
    source_id    TEXT REFERENCES source (id),
    query_id     TEXT NOT NULL,
    discipline   TEXT NOT NULL CHECK (discipline IN ('osint_web', 'osint_feed', 'osint_site', 'osint_academic', 'geoint', 'sensor')),
    -- A sighting belongs to its candidate's run.
    FOREIGN KEY (candidate_id, run_id) REFERENCES candidate (id, run_id)
);

CREATE INDEX sighting_run ON sighting (run_id, id);
CREATE INDEX sighting_candidate ON sighting (candidate_id);

-- A candidate that matched an existing intelligence report at collection time.
-- report_id gains its foreign key when the report table arrives (WP5).
CREATE TABLE reinforcement (
    candidate_id TEXT PRIMARY KEY REFERENCES candidate (id),
    report_id    TEXT NOT NULL,
    matched_by   TEXT NOT NULL CHECK (matched_by IN ('url', 'title'))
);
