--
-- Copyright (c) Microsoft Corporation.
-- Licensed under the MIT License.
--

-- DB schema for storing MLOS benchmarking results.
-- The syntax works for SQLite3, DuckDB, PostgreSQL, and MySQL / MariaDB.

DROP TABLE IF EXISTS trial_telemetry;
DROP TABLE IF EXISTS trial_result;
DROP TABLE IF EXISTS experiment_merge;
DROP TABLE IF EXISTS trial;
DROP TABLE IF EXISTS experiment_metrics;
DROP TABLE IF EXISTS experiment;
DROP TABLE IF EXISTS output_metric;
DROP TABLE IF EXISTS output_metrics;
DROP TABLE IF EXISTS trial_config_value;
DROP TABLE IF EXISTS trial_config;
DROP TABLE IF EXISTS tunable_param;
DROP TABLE IF EXISTS tunable_groups;

-- A table to store the schema of tunable parameters for a given experiment.
-- Tunable parameters and their types, used for merging the data from several experiments.
CREATE TABLE tunable_groups (
    tunable_groups_id INTEGER NOT NULL,
    tunable_groups_uid VARCHAR(255) NOT NULL,   -- A unique ID for this set of tunable params (e.g. a hash of the json encoded configs)

    PRIMARY KEY (tunable_groups_id),
    UNIQUE (tunable_groups_uid)
);

-- Tunable parameters and their types, used for merging the data from several experiments.
-- Records in this table must match the `mlos_bench.tunables.Tunable` class.
CREATE TABLE tunable_param (
    tunable_groups_id INTEGER NOT NULL,
    param_id VARCHAR(255) NOT NULL,
    param_type VARCHAR(32) NOT NULL,  -- One of {int, float, categorical}
    param_default VARCHAR(255),
    param_meta VARCHAR(1023),  -- JSON-encoded metadata (e.g. range or categories).

    -- FIXME? This may still lead to duplicate tunable_params if the same tunable_param is used in multiple tunable_groups sets but others differ.
    PRIMARY KEY (tunable_groups_id, param_id),
    FOREIGN KEY (tunable_groups_id) REFERENCES tunable_groups(tunable_groups_id)
);

-- A named config, which is a collection of config_values
-- (i.e. tunable params that have been assigned a value).
-- Note: One or more trials may be associated with a config
-- (e.g. for repeated trial results for the same config).
CREATE TABLE trial_config (
    config_id INTEGER NOT NULL,
    tunable_groups_id INTEGER NOT NULL, -- The set of tunable params this config is an instance of.
    config_uid VARCHAR(255) NOT NULL,   -- A unique ID for this config (e.g. a hash of the json encoded config)

    PRIMARY KEY (config_id),
    UNIQUE (config_uid),
    FOREIGN KEY (tunable_groups_id) REFERENCES tunable_groups(tunable_groups_id)
);

-- A table to contain an entry for each assigned parameter value in a config.
CREATE TABLE trial_config_value (
    config_id INTEGER NOT NULL,
    param_id VARCHAR(255) NOT NULL,
    param_value VARCHAR(255),

    PRIMARY KEY (config_id, param_id),
    FOREIGN KEY (config_id) REFERENCES trial_config(config_id),
    FOREIGN KEY (param_id) REFERENCES tunable_param(param_id),
);

-- A table to store the schema of possible output scores for trials in a experiment.
-- (as declared by the experiment config).
-- These are one or more scores that the experiment scripts are expected to
-- output upon trial completion.
CREATE TABLE output_metrics (
    output_metrics_id INTEGER NOT NULL,
    output_metrics_uid VARCHAR(255) NOT NULL,   -- A unique ID for this set of output metrics (e.g. a hash of the json encoded configs)

    PRIMARY KEY (output_metrics_id),
    UNIQUE (output_metrics_uid)
);

-- Table to hold the description of individual output metrics for the experiment.
CREATE TABLE output_metric (
    output_metrics_id INTEGER NOT NULL,
    metric_id VARCHAR(255) NOT NULL,
    metric_type VARCHAR(32) NOT NULL,   -- One of {int, float}
    metric_meta VARCHAR(1023),          -- JSON-encoded metadata (e.g. range or categories).

    -- FIXME? This may still lead to duplicate outputs if the same metric is used in multiple output_metric sets but others differ.
    PRIMARY KEY (output_metrics_id, metric_id),
    FOREIGN KEY (output_metrics_id) REFERENCES output_metrics(output_metrics_id)
);

-- A table to store experiment info.
-- Experiments are sets of trials.
CREATE TABLE experiment (
    exp_id VARCHAR(255) NOT NULL,
    descr TEXT,
    tunable_params_id INTEGER NOT NULL,  -- Set of tunable params we're optimizing for this experiment.
    output_metrics_id INTEGER NOT NULL,  -- Metric(s) we're expecting to receive from the trial scripts for this experiment.
    git_repo VARCHAR(255) NOT NULL,
    git_commit VARCHAR(40) NOT NULL,

    PRIMARY KEY (exp_id),
    FOREIGN KEY (output_metrics_id) REFERENCES output_metrics(output_metrics_id),
    FOREIGN KEY (tunable_params_id) REFERENCES tunable_params(tunable_params_id)
);

-- One or more objectives for the experiment to optimize.
CREATE TABLE experiment_objectives (
    exp_id VARCHAR(255) NOT NULL,
    metric_id VARCHAR(255) NOT NULL,
    minimize BOOLEAN NOT NULL,

    PRIMARY KEY (exp_id, metric_id),
    FOREIGN KEY (exp_id) REFERENCES experiment(exp_id)
    FOREIGN KEY (metric_id) REFERENCES output_metrics(metric_id)
);

-- A table to store trial info.
-- Each trial belongs to one experiment (though maybe reused via the merge mechanism), in others.
-- Each trial has a config, and may also have a result, and telemetry data.
CREATE TABLE trial (
    exp_id VARCHAR(255) NOT NULL,
    trial_id INTEGER NOT NULL,
    config_id INTEGER NOT NULL,
    ts_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    ts_end TIMESTAMP,
    -- Should match the text IDs of `mlos_bench.environment.Status` enum:
    status VARCHAR(16) NOT NULL,

    PRIMARY KEY (exp_id, trial_id),
    FOREIGN KEY (exp_id) REFERENCES experiment(exp_id),
    FOREIGN KEY (config_id) REFERENCES trial_config(config_id)
);

CREATE TABLE experiment_merge (
    dest_exp_id VARCHAR(255) NOT NULL,
    dest_trial_id INTEGER NOT NULL,
    source_exp_id VARCHAR(255) NOT NULL,
    source_trial_id INTEGER NOT NULL,

    UNIQUE (dest_exp_id, dest_trial_id, source_exp_id, source_trial_id),

    FOREIGN KEY (dest_exp_id, dest_trial_id)
        REFERENCES trial(exp_id, trial_id),

    FOREIGN KEY (source_exp_id, source_trial_id)
        REFERENCES trial(exp_id, trial_id)
);

-- A table to store final trial result scores (if trial status != FAILED).
-- Note: each trial may have multiple scores (e.g. one for each objective).
-- Each trial score must be associated with a metric_id from the corresponding output_metrics table.
CREATE TABLE trial_result (
    exp_id VARCHAR(255) NOT NULL,
    trial_id INTEGER NOT NULL,
    metric_id VARCHAR(255) NOT NULL,
    metric_value VARCHAR(255),   -- generally expected to be a float, but we leave it as a string for flexibility for now

    PRIMARY KEY (exp_id, trial_id, metric_id),
    FOREIGN KEY (exp_id, trial_id) REFERENCES trial(exp_id, trial_id),
    FOREIGN KEY (metric_id) REFERENCES output_metric(metric_id),
    FOREIGN KEY (exp_id) REFERENCES experiment(exp_id)
);

-- A table to store additional (e.g. intermediary) telemetry data for a trial.
-- Note: these not be associated with a metric_id from the corresponding output_metrics table.
CREATE TABLE trial_telemetry (
    exp_id VARCHAR(255) NOT NULL,
    trial_id INTEGER NOT NULL,
    ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    metric_id VARCHAR(255) NOT NULL,
    metric_value VARCHAR(255),

    UNIQUE (exp_id, trial_id, ts, metric_id),
    FOREIGN KEY (exp_id, trial_id) REFERENCES trial(exp_id, trial_id),
    FOREIGN KEY (exp_id) REFERENCES experiment(exp_id)
);
