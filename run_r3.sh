#!/bin/sh
# Revision 3 experiments (Google Deep Review round 3), about 5 hours; resumable like run_full.sh.
#  1. fat-tree S3: ablation B split into its two parts (paired with ablation B seeds):
#     cooldown removed, deadband kept (rsdn_no_cooldown); deadband removed, cooldown kept (rsdn_relief_bypass)
#  2. backbones: 'Capacity filter only' (ablation A's sequential heuristic) on S3, S5, S9, S11 (paired with Table V)
#  3. backbones: bottleneck drift with V0 = 0.1 as a fix for the long-detour hold (paired with Table V)
set -e
cd "$(dirname "$0")"
mkdir -p results/r3_ablation_b_split results/r3_capacity_only_wan results/r3_bottleneck_drift
./run.sh python3 -m evaluation.experiment --out results/r3_ablation_b_split --topologies fat_tree     --systems rsdn_no_cooldown rsdn_relief_bypass --scenarios S3 --runs 10 | tee -a results/r3_ablation_b_split/campaign.log
./run.sh python3 -m evaluation.experiment --out results/r3_capacity_only_wan --topologies nsfnet internet2 geant     --systems rsdn_capacity_only --scenarios S3 S5 S9 S11 --runs 5 | tee -a results/r3_capacity_only_wan/campaign.log
./run.sh python3 -m evaluation.experiment --out results/r3_bottleneck_drift --topologies nsfnet internet2 geant     --systems rsdn_bottleneck_drift --scenarios S3 S5 S9 S11 --runs 5 | tee -a results/r3_bottleneck_drift/campaign.log
echo "Revision 3 experiments finished."
