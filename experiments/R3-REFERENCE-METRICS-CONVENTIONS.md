# Reference metric conventions — clarification 2026-11-01

This dated clarification preserves the frozen supplement specification and all historical reference values. It resolves arithmetic review v2's comparison finding; it does not amend selection, thresholds, populations or test admission.

| Field | R3 supplement | Existing Kev reference verifier | Comparison condition |
| --- | --- | --- | --- |
| Accuracy | First argmax of raw scores | First argmax of binary64 probabilities | Keep separate unless item-level predictions agree |
| ECE10 correctness | Raw-score prediction | Probability prediction | Same bins alone do not establish the same formula; predictions must also agree |
| Brier sum | Sum over options, mean over questions | Same convention | Same probabilities, gold, population and temperature required |
| NLL | Shifted logsumexp plus score gap | Historical expression can incur cancellation | Same mathematical definition; numerical agreement must be measured |

For scores `[0, 1e-20]` and gold index 1, raw-score prediction is correct, but binary64 softmax rounds both probabilities to 0.5 and the reference first-argmax prediction is incorrect. Pairing this with scores `[0.01, 0]`, gold index 0, also demonstrates differing ECE10 values within the same bin. These are synthetic regressions, not observed dataset discrepancies. Ordinary comparison tests assert zero probability-argmax mismatches before comparing accuracy and ECE10.

The reference verifier and published historical tables remain unchanged. Future comparisons must label these two accuracy/ECE conventions explicitly. The supplement already exports `probability_argmax_mismatch_count`; a nonzero count prevents an assertion of exact metric equivalence. A zero count alone does not verify dataset, mask, option order, temperature or provenance. No new candidate test read was performed for this clarification.
