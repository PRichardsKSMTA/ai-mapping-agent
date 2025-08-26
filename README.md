# ai-mapping-agent
An AI Agent trained on heuristic mapping of specific FreightMath data. The UI uses
[`streamlit-tags`](https://github.com/gagan3012/streamlit-tags) for editable
suggestion pills.

## Configuration

Store your OpenAI credentials in Streamlit's `secrets.toml`.
Create `.streamlit/secrets.toml` at the project root containing:

```toml
OPENAI_API_KEY = "your-openai-key"
```

Streamlit will automatically load this file when running the app.

### Azure AD authentication

For Azure Active Directory login, set the following variables in
`.streamlit/secrets.toml` or your environment:

- `AAD_CLIENT_ID`
- `AAD_TENANT_ID`
- `AAD_REDIRECT_URI`
- `AAD_CLIENT_SECRET`

When registering the Azure app, add a **Web** platform (not SPA) and set the
Streamlit URL as the redirect URI.

Example `.streamlit/secrets.toml`:

```toml
AAD_CLIENT_ID = "your-client-id"
AAD_TENANT_ID = "your-tenant-id"
AAD_REDIRECT_URI = "http://localhost:8501"
AAD_CLIENT_SECRET = "your-client-secret"
```

The same `AAD_CLIENT_SECRET` must be configured in the Streamlit Cloud
deployment's Secrets settings.

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

## Azure Deployment

To run the agent on Azure App Service using a container, push the Docker image to
[Azure Container Registry (ACR)](https://learn.microsoft.com/azure/container-registry/).

### Build and push the image

```bash
# build locally and push to your registry
az acr login --name <acr_name>
docker build -t <acr_login_server>/ai-mapping-agent:latest .
docker push <acr_login_server>/ai-mapping-agent:latest

# or build remotely with ACR
az acr build --registry <acr_name> --image ai-mapping-agent:latest .
```

### Create the Web App

```bash
az webapp create --resource-group <rg> --plan <appservice_plan> \
  --name <app_name> \
  --deployment-container-image-name <acr_login_server>/ai-mapping-agent:latest

# keep the container running
az webapp config set --resource-group <rg> --name <app_name> --always-on true

# supply required secrets
az webapp config appsettings set --resource-group <rg> --name <app_name> --settings \
  OPENAI_API_KEY=<key> \
  AAD_CLIENT_ID=<client_id> AAD_TENANT_ID=<tenant_id> AAD_REDIRECT_URI=<uri> AAD_CLIENT_SECRET=<secret> \
  SQL_SERVER=<server> SQL_DATABASE=<db> SQL_USERNAME=<user> SQL_PASSWORD=<password>
```

See the [App Service container docs](https://learn.microsoft.com/azure/app-service/tutorial-custom-container)
for more details.
