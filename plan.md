# ResilientSDN, revision 4: plan for 24 November 2026

## Where we are (end of 23 Nov)

| Item | State |
|---|---|
| Generalised formulation, Φ\* optimum, cut condition, scenario space | Done, in `paper_rev4/sec_formulation.tex` |
| Randomised sweep (1,945 instances × 7 systems) | Done, in `paper_rev4/sec_sweep_rev4.tex` |
| v3 (duty-cycle trigger), 30 seeds | Done: S7 drops from 32 s to 6 s; 11.8 s per attack on average |
| TCP floor sensitivity | Done: conclusions don't depend on the floor |
| PR #1 (`revision4-generalised-model-and-sweep` → `main`) | Open, mergeable, waiting for review |
| WAN emulation S6 (600 s attacks, 3 WANs × 3 systems × 5 runs) | **Running overnight**, 2/45 done at 23 Nov evening, about 8 h left |
| **Pursuit hold** (new fix for the rolling-attack weakness) | **Code + unit tests done, not yet evaluated** |

**Rule for the day:** nothing CPU-heavy (simulation, sweep, test suite) while Mininet is running.
Load from other work adds 1–10 % packet loss to the emulation. Do the writing tasks whenever the
emulation is still busy.

## Tasks, in order

### 1. Finish the WAN emulation write-up (≈1 h, as soon as the campaign ends)
- Check `results/wan_ext/campaign.log`: 180 rows, loss of the non-attacked runs ≈ 0 %.
- Run `make_assets.py`, then fill `% WAN-EMULATION-PARAGRAPH` in `sec_results_rev4.tex` from
  `generated/wan_ext_summary.csv`. Compare with the simulation's S6 numbers (static 600 s,
  ResilientSDN 46–204 s).
- Run `build.sh`, commit and push (PR #1 updates).
- **If it was interrupted:** rerun `sh run_wan_ext.sh` in WSL as root with `docker/keep_awake.ps1`
  running. Finished runs are skipped.

### 2. Evaluate the pursuit hold (≈½ day: about 1 h of machine time plus analysis and writing)
The sweep's main new weakness is that against a rolling attacker that follows the victims,
ResilientSDN is worse than static routing in 31 % of those instances. The fix (`controller/decision.py`,
`pursuit_*` options, off by default):
- By Proposition 2, a capacity-filtered move leaves the new path ≤ θ at the measured rates.
- So if that path goes above θ within 8 polls, the attack followed the flow.
- The flow is then pinned for 30 polls instead of being moved again.

Systems: `rsdn_pursuit` (ResilientSDN plus the hold) and `resilient_sdn_v4` (v3 plus the hold).
- [ ] Scenario runs: S1, SB, S3, S5–S14 × 4 topologies × 30 seeds for the two new systems
      (`sim.run --systems rsdn_pursuit resilient_sdn_v4`, into `results/sim_v4`).
- [ ] Sweep: rerun the 1,945 instances for the two new systems
      (`sim.sweep --systems rsdn_pursuit resilient_sdn_v4 --out results/sweep_v4`).
- [ ] Success criteria, fixed **before** looking at the results:
  - (a) rolling instances worse than static: 31 % → clearly lower;
  - (b) no loss on constant, timed and pulse patterns (median remaining excess within ±0.02 of v3);
  - (c) no pursuit events in S1, SB or the constant-attack scenarios (false pursuits);
  - (d) S14 time above θ not worse than v3.
- [ ] Sensitivity: `pursuit_limit` 1 vs 2 and window 5 vs 8 polls, on the rolling instances only.
      Report this; do not tune on the test set.
- [ ] Paper:
  - a v4 row in `tab_sweep`, `tab_sweep_pattern` and `tab_v3`;
  - a short "pursuit hold" paragraph and an Algorithm 1 line;
  - update the limitations whether it works or not. **If it fails a criterion, report that.**
- [ ] Add `rsdn_pursuit` and `resilient_sdn_v4` colours and labels to `analysis/style.py`, and
      v4 to `SWEEP_SYS` in `make_assets.py`.

### 3. Emulation evidence for v3/v4 (optional, ≈3–4 h of machine time, run unattended)
v2–v4 are evaluated in simulation only, which is a stated limitation. A minimal Mininet check:
- fat-tree and NSFNET, S3, S7 and S11, systems `resilient_sdn` vs v3 (and v4 if task 2 succeeds),
  5 runs.
- It needs the config flags in a YAML profile per variant and a new results folder.
- Start it **after** tasks 1–2 and keep the laptop idle while it runs.

### 4. Robustness of the sweep (optional, simulation only, ≈1 h of machine time)
- θ ∈ {0.7, 0.9} instead of 0.8, on a 500-instance subsample.
- Larger random graphs (60–100 nodes) on a 300-instance subsample.
- Report as one sentence plus one supplementary table: "the ranking holds / changes when …".

### 5. Paper merge (needs the paper source `paper/`, which is not on this laptop)
- Follow `paper_rev4/MERGE_GUIDE.md`. Each drop-in file says where it goes; check label clashes.
- Proofread the merged PDF end to end. Numbers must match `paper_rev4/generated/`.

### 6. PR
- Push the day's commits to the same branch; ask `hariteja19` to review and merge PR #1.

## Who does what (all three are part-time on other projects)

| Role | Tomorrow |
|---|---|
| Backend & Cloud Engineer | Tasks 1 and 3: emulation runs and their QA (absorbs the missing DevOps/experiment-QA role) |
| Full-Stack Engineer | Task 2: pursuit-hold evaluation and its tests; reviews PR #1 (absorbs QA) |
| Frontend Engineer & Graphic Designer | Figures and tables for tasks 2/4; task 5 merge layout and proofreading (absorbs technical editing) |

There is no dedicated QA, SRE or research engineer. The pre-registered success criteria (task 2)
and the "no CPU load during emulation" rule stand in for the checks a QA person would do.

## Realistic outcome for the day

| | Contents | Fits in one part-time day? |
|---|---|---|
| **Minimum** | Task 1 (WAN emulation written up) + task 2 (pursuit hold evaluated and reported, positive or negative) + push | Yes |
| **Recommended** | Minimum + task 3 started unattended in the evening | Likely |
| **Ideal** | All of 1–6, including the merged paper | No: the merge alone is 1–1.5 days of work (2–3 calendar days) once the paper source is available |

Risks:
- The overnight emulation may be cut short by sleep or the session ending. That pushes task 1 to
  the afternoon and task 3 to the next day.
- The pursuit hold may not meet its criteria. That is still a result: report it in the limitations.
