# ai-mapping-agent
An AI Agent trained on heuristic mapping of specific FreightMath data

## Configuration

Store your OpenAI credentials in Streamlit's `secrets.toml`.
Create `.streamlit/secrets.toml` at the project root containing:

```toml
OPENAI_API_KEY = "your-openai-key"
```

Streamlit will automatically load this file when running the app.

### Database configuration

To enable operation and customer lookups, set the following environment variables
or add them to `.streamlit/secrets.toml`:

- `SQL_SERVER`
- `SQL_DATABASE`
- `SQL_USERNAME`
- `SQL_PASSWORD`

Alternatively, a full connection string may be supplied via
`AZURE_SQL_CONN_STRING`.

## Command Line Interface

Run the mapping pipeline directly from the terminal using `cli.py`:

```bash
python cli.py <template.json> <input.csv|xlsx> <output.json>
```

The script loads the template, auto-maps columns using heuristics, and writes a
new template JSON with those mappings and any resolved formulas.

## Post-processing

Set `ENABLE_POSTPROCESS=1` (via `.env`, `secrets.toml`, or shell) to activate
PIT BID's Power Automate trigger.

Templates may include an optional `postprocess` block; without the flag, mapped
rows are never sent to the configured URL.

Example launch:

```bash
ENABLE_POSTPROCESS=1 streamlit run app.py
# or
python start_postprocess.py
```

Add this variable to your production hosting configuration so Power Automate
flows run; without it, post-processing is skipped. See `docs/template_spec.md`
for details.
