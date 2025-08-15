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

### Customer selection

After choosing an operation, the app lists matching customers and prepends a “+ New Customer” option for one-time bids. Selecting it reveals a plain text field
to enter the customer name; the entry is transient and never written to the
database.

When an existing customer is chosen, a **Customer IDs** multiselect appears only
if that customer has ID values. At least one ID must be selected in that
scenario (up to five are supported). If the chosen customer lacks IDs or “+
New Customer” is used, the ID selector is skipped entirely.

## Command Line Interface

Run the mapping pipeline directly from the terminal using `cli.py`:

```bash
python cli.py <template.json> <input.csv|xlsx> <output.json>
```

Pass one or more `--customer-id` values to attach Customer IDs to a run. The
flag is repeatable and accepts up to five IDs.

```bash
# single ID
python cli.py template.json input.csv output.json --customer-id 12345

# multiple IDs
python cli.py template.json input.csv output.json --customer-id 12345 --customer-id 67890
```

The script loads the template, auto-maps columns using heuristics, and writes a
new template JSON with those mappings and any resolved formulas.

## Post-processing

Templates may include an optional `postprocess` block. Any template with a
`postprocess` block will automatically trigger an HTTP `POST` of the mapped
rows to the configured URL after export.

Example launch:

```bash
streamlit run app.py
# or
python start_postprocess.py
```

See `docs/template_spec.md` for details.

## SharePoint uploads

All SharePoint exports must be uploaded to:

```
/CLIENT  Downloads/Pricing Tools/Customer Bids
```

This path is case-sensitive and includes two spaces between `CLIENT` and `Downloads`. Keep the exact spacing and capitalization to avoid broken links or misplaced files.
