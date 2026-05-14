Merge conflict backups from the `paper-sub` pull.

Resolved:

- `paper_results.local-before-pull.ipynb` was the local root-level paper notebook before the pull conflict. Its local validation metric comparison section was moved into `paper/notebooks/simulation_results.ipynb`, so the backup file can be removed.

Remaining:

- `robojudo.local-before-pull.log` is a historical local RoboJuDo runtime log. It was checked for warning/error/traceback/conflict-marker lines and none were present. The file contains absolute local machine paths and spans multiple run dates, so treat it as merge forensics only, not as a current paper artifact.
