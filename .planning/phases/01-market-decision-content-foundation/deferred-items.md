
## From plan 01-08

- tests/scan/test_discover.py: `test_discover_youtube_inserts_candidates` and `test_other_language_match_is_flagged` fail independently of plan 08 changes (verified with the plan-08 fix reverted). Likely the plan-07 discovery config change (ytsearch_results 60, min_niche_shorts 3 -> 2) read from the live config.yaml by the tests. Not fixed (out of scope).
