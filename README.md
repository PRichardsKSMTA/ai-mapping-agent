# ai-mapping-agent
An AI Agent trained on heuristic mapping of specific FreightMath data

## Configuration

Store your OpenAI credentials in Streamlit's `secrets.toml`.
Create `.streamlit/secrets.toml` at the project root containing:

```toml
OPENAI_API_KEY = "your-openai-key"
```

Streamlit will automatically load this file when running the app.

## Command Line Interface

Run the mapping pipeline directly from the terminal using `cli.py`:

```bash
python cli.py <template.json> <input.csv|xlsx> <output.json>
```

The script loads the template, auto-maps columns using heuristics, and writes a
new template JSON with those mappings and any resolved formulas.

## Post-processing

Templates may include an optional `postprocess` block. When present, the
specified action runs automatically once mapping completes. See
`docs/template_spec.md` for supported types.
