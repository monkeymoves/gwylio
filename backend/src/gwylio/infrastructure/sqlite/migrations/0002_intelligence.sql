-- Migration 0002: the Intelligence register and the submissions that build it.
--
-- Same conventions as 0001. data/submissions/*.json and data/sweeps/*.json
-- are the facts behind every row here (ADR 0002). Enum CHECK lists follow
-- the order of the enums in gwylio.shared.vocabulary and gwylio.intelligence.

-- One ingested submission file; id is the file name without .json.
CREATE TABLE submission (
    id             TEXT PRIMARY KEY,
    position       INTEGER NOT NULL UNIQUE,
    run_id         TEXT REFERENCES scan_run (id),
    analyst        TEXT NOT NULL,
    rubric_version TEXT NOT NULL,
    received_on    TEXT NOT NULL
        CHECK (received_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    method_note    TEXT NOT NULL
);

CREATE TABLE report (
    id                       TEXT PRIMARY KEY,
    title                    TEXT NOT NULL,
    normalised_title         TEXT NOT NULL,
    url                      TEXT NOT NULL,
    canonical_url            TEXT NOT NULL,
    -- The canonical URL with percent escapes upper-cased: what matching compares.
    url_key                  TEXT NOT NULL,
    source_id                TEXT REFERENCES source (id),
    source_name              TEXT NOT NULL,
    actor_id                 TEXT REFERENCES actor (id),
    lane                     TEXT NOT NULL REFERENCES lane (id),
    report_type              TEXT NOT NULL CHECK (report_type IN ('policy', 'legislation', 'research', 'data_release', 'funding', 'partnership', 'international', 'legal', 'environmental', 'market', 'incident')),
    reliability              TEXT NOT NULL CHECK (reliability IN ('A', 'B', 'C', 'D', 'E', 'F')),
    credibility              INTEGER NOT NULL CHECK (credibility BETWEEN 1 AND 6),
    score_evidence           TEXT NOT NULL CHECK (score_evidence IN ('low', 'medium', 'high')),
    score_novelty            TEXT NOT NULL CHECK (score_novelty IN ('low', 'medium', 'high')),
    score_confidence         TEXT NOT NULL CHECK (score_confidence IN ('low', 'medium', 'high')),
    score_potential_impact   TEXT NOT NULL
        CHECK (score_potential_impact IN ('low', 'medium', 'high')),
    score_time_horizon       TEXT NOT NULL
        CHECK (score_time_horizon IN ('immediate', 'near_term', 'medium_term', 'long_term')),
    state                    TEXT NOT NULL CHECK (state IN ('emerging', 'tracking', 'reinforced', 'matured', 'faded', 'parked')),
    bucket                   TEXT NOT NULL CHECK (bucket IN ('brief', 'follow_up', 'watch', 'park')),
    event_horizon            TEXT
        CHECK (event_horizon GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    last_verified            TEXT
        CHECK (last_verified GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    summary                  TEXT NOT NULL,
    notes                    TEXT NOT NULL,
    owner                    TEXT,
    created_on               TEXT NOT NULL
        CHECK (created_on GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    created_run_id           TEXT REFERENCES scan_run (id),
    independent_confirmation INTEGER NOT NULL CHECK (independent_confirmation IN (0, 1))
);

CREATE INDEX report_url_key ON report (url_key, id);
CREATE INDEX report_normalised_title ON report (normalised_title, id);

-- requirement_id names a requirement in any requirement set; the domain checks it.
CREATE TABLE report_assessment (
    report_id      TEXT NOT NULL REFERENCES report (id) ON DELETE CASCADE,
    position       INTEGER NOT NULL,
    requirement_id TEXT NOT NULL,
    direction      TEXT NOT NULL CHECK (direction IN ('supports', 'threatens', 'neutral', 'informs_baseline')),
    PRIMARY KEY (report_id, position),
    UNIQUE (report_id, requirement_id)
);

CREATE INDEX report_assessment_requirement ON report_assessment (requirement_id, report_id);

-- tag_id names a topic, a hazard or a place, by kind.
CREATE TABLE report_tag (
    report_id TEXT NOT NULL REFERENCES report (id) ON DELETE CASCADE,
    kind      TEXT NOT NULL CHECK (kind IN ('topic', 'hazard', 'place')),
    position  INTEGER NOT NULL,
    tag_id    TEXT NOT NULL,
    PRIMARY KEY (report_id, kind, position),
    UNIQUE (report_id, kind, tag_id)
);

CREATE TABLE report_history (
    report_id TEXT NOT NULL REFERENCES report (id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    on_date   TEXT NOT NULL CHECK (on_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'),
    kind      TEXT NOT NULL CHECK (kind IN ('created', 'sighted', 'state_changed', 'verified', 'updated', 'imported', 'faded', 'revived')),
    change    TEXT NOT NULL,
    PRIMARY KEY (report_id, position)
);

-- A sighting counts for one report at most.
CREATE TABLE report_sighting (
    report_id   TEXT NOT NULL REFERENCES report (id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    sighting_id TEXT NOT NULL UNIQUE REFERENCES sighting (id),
    PRIMARY KEY (report_id, position)
);

CREATE TABLE disposition (
    submission_id TEXT NOT NULL REFERENCES submission (id),
    position      INTEGER NOT NULL,
    candidate_id  TEXT NOT NULL REFERENCES candidate (id),
    outcome       TEXT NOT NULL CHECK (outcome IN ('promoted', 'rejected', 'duplicate', 'deferred', 'reinforcement')),
    reason        TEXT NOT NULL,
    report_id     TEXT REFERENCES report (id),
    PRIMARY KEY (submission_id, position),
    UNIQUE (submission_id, candidate_id),
    CHECK (outcome NOT IN ('promoted', 'reinforcement') OR report_id IS NOT NULL)
);

CREATE INDEX disposition_candidate ON disposition (candidate_id);

-- reinforcement.report_id gains its foreign key. SQLite cannot add one with
-- ALTER TABLE, so the table is rebuilt: create, copy, drop, rename.
CREATE TABLE reinforcement_new (
    candidate_id TEXT PRIMARY KEY REFERENCES candidate (id),
    report_id    TEXT NOT NULL REFERENCES report (id),
    matched_by   TEXT NOT NULL CHECK (matched_by IN ('url', 'title'))
);

INSERT INTO reinforcement_new (candidate_id, report_id, matched_by)
    SELECT candidate_id, report_id, matched_by FROM reinforcement;

DROP TABLE reinforcement;

ALTER TABLE reinforcement_new RENAME TO reinforcement;
