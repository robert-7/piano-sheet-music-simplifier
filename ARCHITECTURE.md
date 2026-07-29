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
    C -. compact analysis .- P
    P -- deterministic rewrite --> D[Simplified MusicXML]

    %% Render to PDF
    D -- convert_musicxml_to_pdf --> E[Simplified PDF]

    %% Outputs
    subgraph "Outputs (timestamped)"
        E --> O1[user/output/TIMESTAMP/]
        C --> O1
        P --> O1
        D --> O1
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

Optional: validate or render this diagram locally

* Validate syntax in pre-commit: the repo includes a hook that checks the Mermaid block using [scripts/diagram.sh](scripts/diagram.sh).
* Render an SVG for docs/slides

Try it:

```shell
docker run --rm -u "$(id -u):$(id -g)" -v "$PWD":/data -w /data minlag/mermaid-cli:11.10.1 -i ARCHITECTURE.md -o docs/architecture.svg
```
