"""Campaigns: planned, restartable and auditable sets of runs (D-033, after regime-fusion-gp).

A campaign is planned once (``plan.write_plan``): every task gets an id and a seed, and the plan
freezes digests of the settings, the data files and the libraries. Execution (``execute``)
re-checks the digests, skips tasks whose record is complete and current, writes records
atomically and stops on low disk space. ``collect`` builds one table and refuses mixed digests.
Every configuration planned is appended to the configuration register (trial counting).
"""
