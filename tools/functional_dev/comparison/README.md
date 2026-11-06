# RC1 DEV comparison consumer

The exact consumer passed bounded Astra review: 26 supplied tests and seven adversarial checks, including actual producer receipt emission with mocked execution. SHA256: ebb72d61bd3c7d0605860893803944d0ec9e6e1382283ebd544b7c3b5e9f7903. This is source/schema acceptance, not acceptance of new scientific results.

Invoke compare_dev.py with --reference-catalog pointing to the validated BASE-REUSE.json, --run-root pointing to the remote campaign followup-cpu-separated-rc1 directory, --receipt-layout phased, and --output pointing to the CPU report directory. Run on175 where production artifacts are readable. Do not omit the phased flag: legacy is the default. Source-preserving deployment is required because the consumer uses the fixed evaluator closure on Ceph.

Exit0 means all eight lanes validated conditionally; exit2 means incomplete inputs; exit1 means contradiction. The consumer retains all sizes/seeds, checks publication identity and both inference/scoring receipts, and reconstructs paired metrics using saved arrays. It reads DEV/calibration only. Historical8190/current4726 runtime equivalence remains unestablished; an optional named receipt does not prove it. No TEST authorization or accepted training gain follows from this program's success.

The tests use tiny synthetic fixtures and the existing local evaluator closure. Execute with python3 -B -P test_compare_dev.py and test_phase_receipts.py. They do not run NPU inference. Process reports and review evidence remain local; public conclusions belong in the GitHub Wiki.

The deployed automatic CPU consumer uses watcher.py, watcher-config.json (staged as config.json), and launch.sh. It is running on175 as retained container nga-rc1-dev-comparison, runc, no devices/network, two CPUs. Receipt changes trigger comparison with a600-second fallback; unchanged inputs are skipped. The wrapper stops on contradictions and preserves conditional runtime status. Four synthetic subprocess checks passed; actual DEV consumption is pending. Stage the reviewed VERDICT.json and BASE-REUSE/DEV-VECTORS/SOURCE-PINS beside the consumer. Never launch a duplicate or overwrite a terminal output.
