# Contracts

## Fixed stage paths

Inference writes `/run/nga/output/result`. Export mounts that inference result read-only at the same path and writes `/run/nga/export/result`. Score mounts that export result read-only at the same path and writes `/run/nga/score/result`. Shared model and data inputs retain their paths under `/model` and `/data` across stages. The model directory is a registered model name directly under `/model`; the two existing model mirror roots remain registered.

The inference component hash contributes to output ownership. This source change creates a new prospective component identity; existing runs continue with their original immutable image and owner record.

- The Dockerfile pins the base image. `SOURCE-MANIFEST.json` pins copied legacy source; the build receipt inventories all v4 context files.
- The configuration schema is closed world and admits registered adapters, not commands or caller-selected executable modules.
- Panel scoring checks the pinned manifest, input file bytes, population joins, record receipts and generation identities, and recomputes saved candidate arithmetic with image-local native functions. The manifest pin establishes content identity, not authorship.
- Saved candidate logits cannot reproduce the original full-vocabulary finiteness check or prove fresh inference. The full-panel route does not run a model.
- The entrypoint discards caller `PYTHONPATH` and restores only fixed CANN image paths.
- Training and inference remain incomplete and unqualified; no training or inference qualification is asserted by this score image.
- Current source adds prospective `native-full-label-v2` and `native-panel-export-v2`; `native-panel-export-v1` refuses historical unbound inference. The historical image described in README predates these routes.
- `image_sha256` is a caller-supplied config pin, not a verified observation of the executing image. No image-authentication authority exists in this adapter. Do not treat it as image provenance or use the prospective bridge for inference until a trusted host-side binding is established and independently verified.
- The local three-type CPU fixture tests the config dispatcher and native arithmetic using a test-only tokenizer, test-only model vectors and test-only model mirror root. It does not validate the installed entrypoint, CANN environment, NPU model loading, or any image identity.
