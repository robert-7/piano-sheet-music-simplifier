# Architecture / End-to-end flow

The high-level pipeline below mirrors the CLI sub-commands and outputs. GitHub renders this Mermaid diagram directly in the README; update it when commands change.

```mermaid
flowchart LR
    %% Inputs
    A1[PDF in user/input/*.pdf]
    A2[MusicXML in user/input/*.musicxml]

    %% Conversion: PDF -> MusicXML (Audiveris)
    A1 -- convert_pdf_to_musicxml --> B[MusicXML]

    %% Direct MusicXML path
    A2 --> B

    %% Analyze MusicXML
    B -- generate_analysis_of_musicxml --> C[Analysis JSON]

    %% Simplify MusicXML
    B -- generate_simplified_musicxml --> P[LH Simplification Plan JSON]
    C -. "compact analysis + prescriptiveLH recommendations" .- P
    P -- deterministic rewrite --> D[Simplified MusicXML]

    %% Instrumentation: compare source LH vs plan/simplified LH
    B -. source LH .-> R[Simplification Report JSON]
    P -. plan LH .-> R
    D -. simplified LH .-> R

    %% Observability: per-run index of what was sent, returned, and written
    D -. run characteristics + outcome .-> S[Run Summary JSON]
    R -. highlights .-> S

    %% Render to PDF
    D -- convert_musicxml_to_pdf --> E[Simplified PDF]

    %% Outputs
    subgraph "Outputs (timestamped)"
        E --> O1[user/output/TIMESTAMP/]
        C --> O1
        P --> O1
        D --> O1
        R --> O1
        S --> O1
    end

    %% External tools (behind the commands)
    classDef ext fill:#f7f7f7,stroke:#bbb,color:#333;
    subgraph External Tools
        W[Audiveris]:::ext
        X[OpenAI]:::ext
        Y["MuseScore (preferred)"]:::ext
        Z["LilyPond (optional)"]:::ext
    end

    %% Show tool involvement (informational)
    A1 -. uses .-> W
    B  -. uses .-> X
    D  -. uses .-> Y
    D  -. optional .-> Z
```

## Instrumentation

Every simplification run (both the OpenAI and music21 backends) also emits a
`<stem>_simplification_report.json` alongside its other outputs. The report quantifies how much
the left hand actually changed -- measures preserved vs. changed, `pctChanged`, a texture
histogram, LH note-count delta, and (for the AI path) how many `prescriptiveLH` recommendations
the model followed vs. overrode. An `unmodifiedFlag` is logged as a warning when a run comes back
nearly unchanged. The `compare_runs` sub-command diffs two runs' reports so regressions in
simplification strength are visible run over run.

## Observability artifacts

Each run also leaves a standardized, flat set of debugging artifacts and a single
`run_summary.json` indexing what was sent to the model, what came back, what failed validation,
and what was finally written. The OpenAI path additionally saves prompt inputs, the raw model
output and reasoning (written *before* validation, so a failed run is still inspectable), and a
`validation_report.json`. Naming and layout are owned by
[`src/piano_learning/utils/run_artifacts.py`](../src/piano_learning/utils/run_artifacts.py) and
documented in full in [DEBUGGING.md](DEBUGGING.md).

Optional: validate or render this diagram locally

* Validate syntax in pre-commit: the repo includes a hook that checks the Mermaid block using [scripts/diagram.sh](../scripts/diagram.sh).
* Render an SVG for docs/slides

Try it:

```shell
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/data -w /data minlag/mermaid-cli:11.10.1 -i docs/ARCHITECTURE.md -o docs/architecture.svg
```
