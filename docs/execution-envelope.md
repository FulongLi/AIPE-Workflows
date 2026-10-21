# Specialist execution envelope v0.1

Every adapter in AIPE-Workflows returns one `ExecutionEnvelope`
(`aipe_workflows.engine.envelope`). It is the common contract between the
workflow engine and specialist capabilities, and it maps one-to-one onto
AIPE-Core v0.1 evidence, simulation-run and validation-check records. It does
not replace the Core Engineering State schema; it is a versioned *workflow
extension* that is translated into Core objects by `engineering_state.apply_proposal`.

| Field | Meaning |
| --- | --- |
| `task_id`, `task_version` | workflow task identity and adapter version |
| `capability_id` | Registry id of the specialist repository that performed the work |
| `tool` | `{id, version, name}` attribution of the actual engine (e.g. `tool.ngspice` 47); ids follow the Core id pattern |
| `status` | `completed`, `failed`, `blocked`, `skipped`; only `completed` with no error diagnostics is used downstream |
| `started_at`, `finished_at` | real UTC timestamps of the execution |
| `source_state_id`, `source_state_sha256` | identity and hash of the Engineering State the task consumed |
| `inputs` | SI quantities and references actually used |
| `outputs` | small validated summary values (no arrays) exposed to downstream tasks via `$task.<id>.<output>` |
| `model` | `{id, version, validity_range, assumptions}` |
| `environment` | tool/library versions and platform |
| `verification` | numerical checks: convergence, periodicity, energy balance, comparison with references |
| `evidence_kind` | Core evidence kind (`assumption`, `analytical`, `simulation`, `measurement`, `source`) |
| `gate` | verification category the result belongs to |
| `artifacts` | `{uri, media_type, sha256, description, role}` references; large data stays in files |
| `diagnostics` | structured warnings and errors |
| `approval_required` | actions needing a human decision |
| `state_proposal` | proposed Engineering State change (below) |
| `input_hash` | hash of inputs, model, tool and parameters; drives selective re-execution |

## State proposal

```json
{
  "evidence": [ ...Core evidence records... ],
  "set": [ {"path": "control", "value": {...}} ],
  "append": [ {"path": "magnetics", "value": {...}}, {"path": "simulation.runs", "value": {...}}, {"path": "validation.checks", "value": {...}} ],
  "extensions": { "aipe.workflows.dab": {...} },
  "status": { "simulation": "completed", "validation": "simulated", "architecture_stage": "candidate", "converter_design_status": "candidate" },
  "updated_at": "2026-10-21T13:00:00Z"
}
```

Rules enforced before a proposal is committed: new evidence ids are unique and
well formed; every object written carries `evidence_refs` that resolve; existing
evidence is never removed; extension keys are namespaced; the resulting state
passes AIPE-Core's own `scripts/validate.py`. Each accepted proposal becomes a
new file `state/state-NNN.json`; earlier versions are never overwritten.

## Status semantics

A `completed` envelope with a passing simulation check lets the Engineering
State reach `validation.status = simulated`. Nothing in this engine can set
`measured` or `reviewed`; those require measurement records and human review
outside the software workflow. A failed solver, a run that did not reach
periodic steady state, or a mismatch against the analytical reference yields
`status = failed` and blocks downstream tasks.
