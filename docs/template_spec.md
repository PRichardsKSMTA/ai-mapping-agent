# Template Spec (v2)

*Last updated: 2025-07-23*

The **AI Mapping Agent** ingests *template definition* files that tell the app:

1. **What** the destination workbook looks like (columns, sheets, look-ups, formulas).  
2. **How many mapping passes** are required to translate a user’s raw file into that shape.  
3. **Where user input is expected** (e.g., custom computed expressions).

This document describes the **minimal, schema-agnostic JSON format** (v2) accepted by the validator in `schemas/template_v2.py`.

---

## 1 Top-level keys

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `template_name` | `string` | ✅ | Human-readable name; slugified to lowercase kebab-case filename (spaces/underscores → `-`). |
| `layers` | `array<Layer>` | ✅ | Ordered list of mapping passes. |
| *(any)* | *any* | optional | Extra metadata preserved for back-compat (e.g., `fields`, `accounts`). |

**Rule:** anything outside `layers` is **metadata only**—never assumed by the engine.

---

## 2 Layer object

Every object inside `layers` *must* have a `type` key.  
The validator dispatches to a specific Pydantic model based on that type.

```jsonc
{
  "type": "header" | "lookup" | "computed" | "your_future_type",
  // …type-specific properties…
}
````

### 2.1 Common optional keys

| Key           | Type     | Purpose                                                  |
| ------------- | -------- | -------------------------------------------------------- |
| `sheet`       | `string` | Explicit sheet name if the template spans multiple tabs. |
| `description` | `string` | UI tooltip; no runtime effect.                           |

---

## 3 Built-in layer types

### 3.1 `header`

> Single-pass mapping of client header names → template header names.

```jsonc
{
  "type": "header",
  "sheet": "BID",          // optional
  "fields": [
    { "key": "Lane ID",  "required": true },
    { "key": "Orig Zip", "required": true,  "notes": "Five or three digits" },
    { "key": "Dest Zip", "required": true }
  ]
}
```

#### `FieldSpec`

| Key        | Type     | Required | Default    | Notes                                           |
| ---------- | -------- | -------- | ---------- | ----------------------------------------------- |
| `key`      | `string` | ✅        | —          | Destination column label.                       |
| `type`     | `string` | optional | `"string"` | Primitive hint (`string`, `number`, `date`, …). |
| `required` | `bool`   | optional | `false`    | If `true`, UI marks as mandatory.               |
| `notes`    | `string` | optional | —          | Shown as tooltip.                               |

---

### 3.2 `lookup`

> Map a source value to a controlled vocabulary (e.g., GL names → standard COA).

```jsonc
{
  "type": "lookup",
  "sheet": "Accounts",
  "source_field": "GL_NAME",
  "target_field": "GL_NAME",
  "dictionary_sheet": "StandardAccounts"
}
```

| Key                | Type     | Required | Notes                                                    |
| ------------------ | -------- | -------- | -------------------------------------------------------- |
| `source_field`     | `string` | ✅        | Column in the *client* file.                             |
| `target_field`     | `string` | ✅        | Column in the *template* that receives the mapped value. |
| `dictionary_sheet` | `string` | ✅        | Sheet (or key) containing the authorised list.           |

---

### 3.3 `computed`

> Create or transform a destination column when it cannot be mapped 1-to-1.

Supported **`strategy`** values:

| Strategy       | Purpose                                                         |
|----------------|-----------------------------------------------------------------|
| `first_available` | *(default)* Pick from template’s candidate rules automatically. |
| `user_defined`    | Launches a **Formula Dialog** for free-form expression building. |

```jsonc
{
  "type": "computed",
  "target_field": "Q2_PROFIT",
  "formula": { "strategy": "user_defined" }
}
```
### At run-time, the Formula Dialog provides:

1. Pills for each column + operators (+ − × ÷ ( )).

2. Free-form text editor so users can mix typing and clicks.

3. Live preview on the first 5 rows.

4. **Save** back to the mapping JSON under the computed layer.

---

If `strategy` =`"user_defined"` the `candidates` array **may be omitted**.
At run-time the user builds an expression; the engine stores its resolution:

```jsonc
{
  "resolved": true,
  "method": "derived",
  "expression": "df['2025-06'] - df['2025-05']",
  "source_cols": ["2025-06", "2025-05"]
}
```

#### `formula` keys

| Key            | Type                                              | Required    | Default             | Notes                                         |
| -------------- | ------------------------------------------------- | ----------- | ------------------- | --------------------------------------------- |
| `strategy`     | `"first_available" \| "user_defined" \| "always"` | ✅           | `"first_available"` | When to evaluate the expression.              |
| `candidates`   | `array<object>`                                   | Conditional | —                   | Ordered tests for *direct* / *derived* rules. |
| `expression`   | `string`                                          | Conditional | —                   | Pythonic arithmetic using `$PLACEHOLDERS`.    |
| `dependencies` | `object`                                          | Conditional | —                   | Maps placeholders to header variants.         |

### 3.4  `postprocess` (optional, top-level)

```jsonc
"postprocess": {
  "type": "sql_insert",
  "connection": "Driver={ODBC Driver 18 for SQL Server};Server=tcp:demo.database.windows.net;Encrypt=yes;",
  "table": "dbo.MAPPED_OUTPUT",
  "column_map": { "GL_ID": "GL_ID", "NET_CHANGE": "NET_CHANGE" }
}
```

Supported **`type`** values:

| Type            | Purpose                                   |
|-----------------|--------------------------------------------|
| `excel_template`| Fill an Excel workbook using mapped data.  |
| `sql_insert`    | Insert rows into a SQL table via ODBC.     |
| `http_request`  | Send mapped data as an HTTP request body.  |
| `python_script` | Execute inline Python code with `df` bound.|

---

## 4 Extending with new layer types

1. Define a **new Pydantic model** in `schemas/template_v2.py`.
2. Add it to the `Layer` union.
3. Implement a helper in `app_utils.mapping.<your_layer>.py`.
4. Update UI to call that helper when `layer.type == "your_type"`.

---

## 5 Examples

### 5.1 PIT *BID* (header-only)

```jsonc
{
  "template_name": "pit-bid",
  "layers": [
    {
      "type": "header",
      "sheet": "BID",
      "fields": [
        { "key": "Lane ID",  "required": true },
        { "key": "Orig Zip", "required": true },
        { "key": "Dest Zip", "required": true }
      ]
    }
  ]
}
```

### 5.2 Standard COA (header + lookup + computed)

See `templates/standard-coa.json`.

### 5.3 Multi-period profit (user-defined computed)

```jsonc
{
  "template_name": "multi-period-profit",
  "layers": [
    {
      "type": "header",
      "fields": [{ "key": "Account" }]
    },
    {
      "type": "computed",
      "target_field": "Q2_PROFIT",
      "formula": { "strategy": "user_defined" }
    }
  ]
}
```

---

## 6 File-naming convention

* Save each template as **kebab-case** (`pit-bid.json`, `standard-coa.json`).
* The validator doesn’t care, but kebab-case improves CLI/URL readability.

---

## 7 Versioning & compatibility

* This spec is **v2.1**.
* Loader auto-detects legacy v1 templates (`fields` + `accounts`) and injects equivalent `layers` at runtime.
* Future specs will bump to v3 only if breaking changes are unavoidable.

---

## 8 Changelog

| Date       | Version | Change                                                                                    |
| ---------- | ------- | ----------------------------------------------------------------------------------------- |
| 2025-07-23 | 2.1     | Added `strategy: "user_defined"` for computed layers; clarified runtime expression store. |
| 2025-07-22 | 2.0     | Initial multilayer spec; removed mandatory `accounts`.                                    |

---
