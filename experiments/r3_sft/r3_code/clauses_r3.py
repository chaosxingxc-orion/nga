"""Registry of the R3-SFT-PREREG clauses that change a number, and the test that asserts each (sec 10.5, R0 sec 11.8 item 3).

A clause is IN FORCE only when a test naming it exists and asserts it: the registry maps a clause to (test file, test function);
`clause_status()` parses those files with `ast` (no import, so torch-dependent test files can be listed without torch) and reports a
clause as in force iff the function is defined at the top level of the file. A clause registered with None has no test and is reported
NOT in force. The report header carries both lists.
"""
import ast
import os

HERE = os.path.dirname(os.path.abspath(__file__))

CLAUSES = {
    # --- data, readout and prompt ---
    "3.4 training-time augmentation equals Kev's own functions (all train records)": ("test_r3_data.py", "test_augmentation_matches_kev_on_every_train_record"),
    "10.4 pre-training: augmentation byte-identical to Kev's functions on 20 train records": ("test_prechecks_r3.py", "test_s10_4_pretraining_augmentation_is_byte_identical_to_kevs_own_functions_on_20_train_records"),
    "7.3 K2 training score equals the evaluation scorer's s": ("test_train_r3.py", "test_k2_equals_evaluation_scorer"),
    "7.2 loss on the response tokens only, no EOS": ("test_train_r3.py", "test_loss_mask_response_only_and_gathered_logits_equal_full"),
    "14.2 right-padding invariance of the scorer": ("test_train_r3.py", "test_right_padding_invariance"),
    # --- Track K ---
    "4.1/4.2 headline: first maximal index, R0-rule accuracy and tie count beside": ("test_full_eval_r3.py", "test_s4_2_headline_is_first_max_with_r0_rule_and_tie_count_beside"),
    "4.4 operator column: tau fitted on decision-v7 calibration only, harness label": ("test_variants_r3.py", "test_s4_4_operator_tau_is_fitted_on_calibration_rows_only"),
    "4.5 permutation flip: same-order excluded and counted": ("test_variants_r3.py", "test_s4_5_same_order_pairs_are_excluded_and_counted_on_dev"),
    "4.5 permutation flip: by level id, tied pairs dropped": ("test_variants_r3.py", "test_s4_5_flip_is_by_level_id_drops_ties_and_excludes_same_order"),
    "4.5 permutation flip: discrimination counterpart beside": ("test_variants_r3.py", "test_s4_5_input_ignoring_classifier_scores_zero_and_discrimination_counterpart_is_reported"),
    "4.6 none-of-the-above pair: parents, optima, both-sides-right": ("test_variants_r3.py", "test_s4_6_unconstrained_optima_always_nota_and_never_nota_score_zero_on_both_sides_right"),
    "4.7 secondary metrics gate nothing": ("test_variants_r3.py", "test_s4_7_secondary_metrics_return_no_verdict_keys"),
    "4.8 flip rate of trained arms labelled a sanity metric": ("test_variants_r3.py", "test_s4_8_label_is_invariance_only_for_k0"),
    "5.1 constant arm and its fallback tiers": ("test_prechecks_r3.py", "test_s5_1_constant_uses_question_tier_then_position_tier_then_position_zero"),
    "5.4 uniform arm": ("test_prechecks_r3.py", "test_s5_4_uniform_headline_equals_share_of_gold_at_position_0_and_r0_convention_is_zero"),
    "5.2/5.3 question-only and empty-state arms are the scored model with the input dropped / blanked": ("test_full_eval_r3.py", "test_s5_2_s5_3_question_only_and_empty_state_use_the_scored_model_with_input_modes"),
    "2.2 Kev partitions are the hash-pinned files of KEV/manifest.json": ("test_prechecks_r3.py", "test_s2_2_kev_files_match_the_manifest_hashes_and_a_changed_file_is_refused"),
    "7.9 K1-QO is scored with the state dropped": ("test_full_eval_r3.py", "test_s7_9_k1_qo_is_scored_with_the_state_dropped"),
    "10.2 tokens/s/chip and examples/s/chip with the chip count stated; carried by the heartbeat (CLAUDE.md sec 9)": ("test_full_eval_r3.py", "test_s10_2_tokens_per_second_per_chip_are_reported_and_ride_the_heartbeat"),
    "7.7 / 10.2 run directory bound to one model; data sha256s and per-chip throughput recorded": ("test_full_eval_r3.py", "test_s7_7_run_directory_is_bound_to_one_model_and_records_data_hashes_and_throughput"),
    "6.2 arm-level roll-up: passes only if every seed passes (selection tooling)": ("test_select_r3.py", "test_s6_2_arm_lines_pass_only_if_every_seed_passes"),
    "10.1 every rate carries its n, accuracies their tie count, flip rates dropped pairs and C-branch rate": ("test_variants_r3.py", "test_s10_1_flip_rate_carries_n_dropped_pairs_and_c_branch_rate"),
    # --- pre-number checks ---
    "10.4(a) constant + uniform first, gold-position distribution, 5,416 of 15,576": ("test_prechecks_r3.py", "test_s10_4a_constant_and_uniform_first_with_gold_positions_per_partition"),
    "10.4(b) rendered prompt hashes of clean / permuted / NOTA variants differ": ("test_prechecks_r3.py", "test_s10_4b_prompt_hashes_of_clean_permuted_and_both_nota_variants_all_differ"),
    "10.4(c) stored argmax recomputed from stored s_i on 20 rows": ("test_prechecks_r3.py", "test_s10_4c_stored_argmax_is_recomputed_from_stored_s_on_20_rows"),
    "10.4 a failed pre-number check aborts the run": ("test_full_eval_r3.py", "test_s10_4_a_failed_precheck_aborts_the_run_before_any_number"),
    # --- test lock ---
    "8.4 test lock: FINAL.json naming, one read per partition, TEST-READS.log line": ("test_testlock_r3.py", "test_s8_4_named_model_reads_once_and_the_log_line_has_the_required_fields"),
    "8.4 test lock: the loader refuses a test partition without a ticket": ("test_testlock_r3.py", "test_s8_4_loader_refuses_a_test_partition_without_a_ticket"),
    "8.4 test lock: unmerged-adapter identity = adapter files + base revision": ("test_testlock_r3.py", "test_s8_4_adapter_identity_hashes_adapter_files_and_base_revision"),
    "8.4 one test lock only: the weaker guard_split is retired, the older path refuses test": ("test_testlock_r3.py", "test_s8_4_there_is_one_test_lock_the_retired_guard_and_the_older_path_refuse_test"),
    "8.4 no test partition is opened by a normal run": ("test_full_eval_r3.py", "test_s8_4_a_dry_run_opens_no_test_partition_and_refuses_one"),
    # --- Track T ---
    "2.5 selection / report halves by the r3sel hash; cell totals": ("test_track_t_r3.py", "test_s2_5_halves_by_r3sel_hash_and_totals_match_the_prereg"),
    "2.6 tau fitted only on the r3tau carve-out": ("test_track_t_r3.py", "test_s2_6_tau_is_fitted_only_on_the_r3tau_carveout"),
    "6.1 tie rules on Track T (floor, flip, move)": ("test_track_t_r3.py", "test_s6_1_tie_rules_floor_flip_and_move"),
    "6.2 B-1 operator accuracy >= constant + 10 points, per source": ("test_track_t_r3.py", "test_s6_2_b1_margin_and_source_rollup"),
    "6.2 B-2 pass / void / fail by the R0 sec 13.5 gap rule": ("test_track_t_r3.py", "test_s6_2_b2_pass_void_fail_gap_rule"),
    "6.2 B-2 (T3) on typed-decisions": ("test_track_t_r3.py", "test_s6_2_b2_t3_is_evaluated_for_typed_decisions_only"),
    "6.2 B-3 followed > 30% and >= 10 points above the T1 flip": ("test_track_t_r3.py", "test_s6_2_b3_followed_rate_rule"),
    "6.2 a line passes for an arm only if it passes for every seed": ("test_track_t_r3.py", "test_s6_2_a_line_passes_for_an_arm_only_if_every_seed_passes"),
    "6.3 B-4 and ruling 3 (not admissible where the trained model fails B-1)": ("test_track_t_r3.py", "test_s6_3_b4_pass_fail_not_admissible_and_void"),
    "6.3 / 14.5 item 1 R0 configuration (tau on the full group70 train side, whole held-out side, R0's published tie rule)": ("test_track_t_r3.py", "test_s6_3_r0_configuration_uses_the_full_train_side_and_the_whole_heldout_side"),
    "6.5(i) harness identity: pins read from R0, snapshot byte-identical to live r0_code": ("test_harness_identity_r3.py", "test_s14_5_1_pins_are_read_from_r0_and_every_readout_path_file_is_pinned"),
    "6.5(i) shard assignment is the pinned function and reproduces R0's n_shard_records": ("test_harness_identity_r3.py", "test_s14_5_1_shard_assignment_is_the_pinned_function_and_reproduces_what_r0_recorded"),
    "6.5(i) identical -> IDENTICAL; a difference under the fully pinned configuration -> DEFECT (stops the round)": ("test_harness_identity_r3.py", "test_s14_5_1_identical_readouts_give_identical_and_a_difference_under_full_pins_is_a_defect"),
    "6.5(i) a difference traceable to an unpinnable element is a recorded gap, not a defect": ("test_harness_identity_r3.py", "test_s14_5_1_a_difference_traceable_to_an_unpinnable_element_is_a_recorded_gap_not_a_defect"),
    "6.5(i) a pinnable element that differs is a pin violation; a short run is incomplete": ("test_harness_identity_r3.py", "test_s14_5_1_a_pinnable_element_that_differs_is_a_pin_violation_and_a_short_run_is_incomplete"),
    "6.5(i) derived report compared leaf by leaf with the published one": ("test_harness_identity_r3.py", "test_s14_5_1_report_comparison_is_exact_on_the_published_report_and_names_the_gap_paths"),
    "6.5(i) a killed shard restarts its partial files, never resumes them": ("test_harness_identity_r3.py", "test_s14_5_1_a_killed_shard_restarts_its_partial_files_from_scratch_never_resumes_them"),
    "6.5(ii) erratum measurement: metric by metric, no pass bar, needs the (i) control": ("test_harness_identity_r3.py", "test_s14_5_1_erratum_difference_is_metric_by_metric_with_no_pass_bar_and_needs_the_control"),
    "14.5 item 1: no report of record names a source path under the (i) derivation directory": ("test_harness_identity_r3.py", "test_s14_5_1_no_report_of_record_names_a_source_path_under_harness_identity"),
    "14.6 item 3 fp32 admissibility bar of the scorer of record (null gate, (i'), (ii'), (iii'), discrimination counterpart)": ("test_scorer_r3.py", "test_fp32_candidates_meet_the_amendment6_bar"),
    "14.9 item 5 near-tie census with every readout of record, listed with top-2 candidates; 14.6 item 4 duplicate safeguard declared vacuous and audited": ("test_full_eval_r3.py", "test_s14_9_5_near_tie_census_rides_with_every_headline_and_the_duplicate_safeguard_is_audited"),
    "14.6 item 2 / 14.9 item 3 scorer of record at the entry point: rightpad, float32, HF32 off, token_budget 16384; record-grade guard": ("test_full_eval_r3.py", "test_s14_6_2_s14_9_3_scorer_of_record_is_rightpad_fp32_hf32_off_budget_16384_and_the_entry_point_enforces_it"),
    "11.2 several units sharing one run dir: per-unit marker, perf file and heartbeat tag": ("test_full_eval_r3.py", "test_s11_2_units_sharing_one_run_dir_have_their_own_marker_perf_file_and_heartbeat_tag"),
    "11.2 Track K scored in pieces on several units (k_score) and merged without rescoring equals one pass": ("test_full_eval_r3.py", "test_s11_2_track_k_can_be_scored_in_pieces_on_several_units_and_merged_without_rescoring"),
    "14.5 item 1 (ii) erratum: completeness (shared keys == records_needed(R0)) and readout provenance (per-file manifest, per-row model stamp, model sha recomputed from the weights)": ("test_harness_identity_r3.py", "test_s14_5_1_erratum_refuses_readouts_of_another_model_behind_a_forged_run_identity"),
    "14.5 item 1 (ii) erratum refuses a partial fp32 side": ("test_harness_identity_r3.py", "test_s14_5_1_erratum_refuses_a_partial_fp32_side_and_names_what_is_missing"),
    "14.5 item 1 (ii) producers stamp every readout row and write a verifying manifest": ("test_full_eval_r3.py", "test_s14_5_1_every_readout_row_is_stamped_and_every_producing_run_writes_a_manifest_that_verifies"),
    "14.11 item 4 R0-configuration fp32 re-score: keys == records_needed(R0) per role, provenance, resume to completeness (no partial-with-a-note)": ("test_r0rescore.py", "test_s14_5_1_r0_rescore_refuses_a_worker_that_died_mid_role_and_the_scorer_that_is_not_the_scorer_of_record"),
    "14.11 item 4 R0 re-score chips are claimed only from the free list": ("test_r0rescore.py", "test_s14_5_1_r0_rescore_claim_takes_only_chips_listed_free"),
    "14.11 item 4 R0 re-score: a dead claimant yields a terminal marker (exit_code 1), never silence": ("test_r0rescore.py", "test_s14_11_4_a_dead_claimant_leaves_a_terminal_marker_not_silence"),
    "14.11 item 4 R0 re-score: executed code equals hashed code (r0_code live modules), chip release is loud": ("test_r0rescore.py", "test_s14_11_4_executed_code_is_the_hashed_code_and_a_release_failure_is_loud"),
    "5 Track T degenerate arms (constant, uniform, empty-input, question-only)": ("test_track_t_r3.py", "test_s5_track_t_degenerate_arms_are_present_and_uniform_is_all_ties"),
    # --- selection and decision lines ---
    "8.2(a) paired bootstrap on combined dev, rng 20261030, 10,000 resamples, 90% CI": ("test_select_r3.py", "test_s8_2a_paired_bootstrap_is_reproducible_and_matches_a_direct_computation"),
    "8.2(b) neither suite's seed-mean dev accuracy drops by more than 1.0 point": ("test_select_r3.py", "test_s8_2b_suite_drop_boundary"),
    "8.2(c) gating cells and the 2-point flip rise": ("test_select_r3.py", "test_s8_2c_gating_cells_and_flip_rise"),
    "8.3 per-seed accuracies, CI and discordant counts reported": ("test_select_r3.py", "test_s8_3_compare_reports_seeds_ci_and_discordant_counts"),
    "9.1 K-align": ("test_select_r3.py", "test_s9_1_k_align"),
    "9.2 K-floor": ("test_select_r3.py", "test_s9_2_k_floor"),
    "9.3 K-ladder": ("test_select_r3.py", "test_s9_3_k_ladder"),
    # --- clauses with no test in this harness (reported NOT in force) ---
    "7.5 K4 lr choice and 7.6 ladder recipe (training side)": None,
    "11.3 kernel gate (amendment 1 and 4)": None,
}


def _defined_tests(path):
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return set()
    return {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}


def clause_status(clauses=None, directory=HERE):
    """{"in_force": {clause: 'file::test'}, "not_in_force": [clause, ...]} (sec 10.5)."""
    clauses = CLAUSES if clauses is None else clauses
    cache, in_force = {}, {}
    for clause, spec in clauses.items():
        if spec is None:
            continue
        fn, test = spec
        if fn not in cache:
            cache[fn] = _defined_tests(os.path.join(directory, fn))
        if test in cache[fn]:
            in_force[clause] = f"{fn}::{test}"
    return {"in_force": in_force, "not_in_force": sorted(c for c in clauses if c not in in_force)}
