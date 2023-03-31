#
# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.
#
"""
Saving and restoring the benchmark data using SQLAlchemy.
"""

import logging
from typing import List, Tuple

from sqlalchemy import text

from mlos_bench.tunables import TunableGroups
from mlos_bench.storage.base_storage import Storage
from mlos_bench.storage.sql_trial import Trial

_LOG = logging.getLogger(__name__)


class Experiment(Storage.Experiment):
    """
    Logic for retrieving and storing the results of a single experiment.
    """

    def __enter__(self):
        super().__enter__()
        with self._engine.begin() as conn:
            git_info = conn.execute(
                text("""
                    SELECT git_repo, git_commit FROM experiment_config
                    WHERE exp_id = :exp_id
                """),
                {"exp_id": self._experiment_id}
            ).fetchone()
            if git_info is None:
                conn.execute(
                    text("""
                        INSERT INTO experiment_config (exp_id, descr, git_repo, git_commit)
                        VALUES (:exp_id, :descr, :git_repo, :git_commit)
                    """),
                    {
                        "exp_id": self._experiment_id,
                        "descr": None,
                        "git_repo": self._git_repo,
                        "git_commit": self._git_commit
                    }
                )
            else:
                if git_info.git_commit != self._git_commit:
                    _LOG.warning("Experiment %s git expected: %s %s",
                                 self, git_info.git_repo, git_info.git_commit)
                trial = conn.execute(
                    text("""
                        SELECT MAX(trial_id) as trial_id
                        FROM trial_status WHERE exp_id = :exp_id
                    """),
                    {"exp_id": self._experiment_id}
                ).fetchone()
                if trial is not None:
                    self._trial_id = trial.trial_id + 1
        return self

    def merge(self, experiment_ids: List[str]):
        _LOG.info("Merge: %s <- %s", self._experiment_id, experiment_ids)
        raise NotImplementedError()

    def load(self, opt_target: str) -> Tuple[List[dict], List[float]]:
        configs = []
        scores = []
        with self._engine.connect() as conn:
            cur_trials = conn.execute(
                text("""
                    SELECT s.trial_id, r.param_value
                    FROM trial_status AS s
                    JOIN trial_results AS r ON (s.exp_id = r.exp_id AND s.trial_id = r.trial_id)
                    WHERE s.exp_id = :exp_id AND s.status = 'SUCCEEDED' AND r.param_id = :param_id
                    ORDER BY s.trial_id ASC
                """),
                {"exp_id": self._experiment_id, "param_id": opt_target}
            )
            for trial in cur_trials:
                tunables = self._get_tunables(conn, trial.trial_id)
                configs.append(tunables)
                scores.append(float(trial.param_value))
            return (configs, scores)

    def _get_tunables(self, conn, trial_id: int) -> dict:
        cur_tunables = conn.execute(
            text("""
                SELECT param_id, param_value FROM trial_config
                WHERE exp_id = :exp_id AND trial_id = :trial_id
            """),
            {"exp_id": self._experiment_id, "trial_id": trial_id}
        )
        return {row.param_id: row.param_value for row in cur_tunables}

    def pending(self):
        _LOG.info("Retrieve pending trials for: %s", self._experiment_id)
        with self._engine.connect() as conn:
            cur_trials = conn.execute(
                text("""
                    SELECT trial_id FROM trial_status
                    WHERE exp_id = :exp_id AND ts_end IS NULL
                """),
                {"exp_id": self._experiment_id}
            )
            for trial in cur_trials:
                # Reset .is_updated flag after assignment!
                tunables = self._tunables.copy().assign(
                    self._get_tunables(conn, trial.trial_id)).reset()
                yield Trial(self._engine, tunables, self._experiment_id, trial.trial_id)

    def trial(self, tunables: TunableGroups):
        _LOG.debug("Updating trial: %s:%d", self._experiment_id, self._trial_id)
        with self._engine.begin() as conn:
            try:
                conn.execute(
                    text("""
                        INSERT INTO trial_status (exp_id, trial_id, status)
                        VALUES (:exp_id, :trial_id, 'PENDING')
                    """),
                    {"exp_id": self._experiment_id, "trial_id": self._trial_id}
                )
                conn.execute(
                    text("""
                        INSERT INTO trial_config (exp_id, trial_id, param_id, param_value)
                        VALUES (:exp_id, :trial_id, :param_id, :param_value)
                    """),
                    [
                        {
                            "exp_id": self._experiment_id,
                            "trial_id": self._trial_id,
                            "param_id": tunable.name,
                            "param_value": None if tunable.value is None else str(tunable.value)
                        }
                        for (tunable, _group) in tunables
                    ]
                )
                trial = Trial(self._engine, tunables, self._experiment_id, self._trial_id)
                self._trial_id += 1
                return trial
            except Exception:
                conn.rollback()
                raise
