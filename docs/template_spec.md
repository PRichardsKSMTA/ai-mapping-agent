# Template Spec (v2)

*Last updated: 2025-07-22*

The **AI Mapping Agent** ingests *template definition* files that tell the app:

1. **What** the destination workbook looks like (columns, sheets, look-ups, formulas).  
2. **How many mapping passes** are required to translate a user’s raw file into that shape.

This document describes the **minimal, schema-agnostic JSON format** (v2) accepted by the validator in `schemas/template_v2.py`.

---

## 1  Top-level keys

| Key | Type | Required | Notes |
|-----|------|----------|-------|
| `template_name` | `string` | ✅ | Human-readable name; will be slugified into a file name (kebab-case). |
| `layers` | `array<Layer>` | ✅ | Ordered list of mapping passes. |
| *(any)* | *any* | optional | Extra keys are preserved (e.g., `fields`, `accounts`) for back-compat. |

**Rule:** anything outside `layers` is **metadata only**—it is never assumed by the core engine.

---

## 2  Layer object

Every object inside `layers` *must* have a `type` field.  
The validator dispatches to a specific Pydantic model based on that type.

```jsonc
{
  "type": "header" | "lookup" | "computed" | "your_future_type",
  // ...type-specific properties...
}
````

### 2.1  Common optional keys

| Key           | Type     | Purpose                                                  |
| ------------- | -------- | -------------------------------------------------------- |
| `sheet`       | `string` | Explicit sheet name if the template spans multiple tabs. |
| `description` | `string` | UI tooltip; no runtime effect.                           |

---

## 3  Built-in layer types

### 3.1  `header`

> Single-pass mapping of client header names → template header names.

```jsonc
{
  "type": "header",
  "sheet": "BID",            // optional
  "fields": [
    { "key": "Lane ID",  "required": true },
    { "key": "Orig Zip", "required": true,  "notes": "Five or three digits" },
    { "key": "Dest Zip", "required": true }
  ]
}
```

#### FieldSpec

| Key        | Type     | Required | Default    | Notes                                           |
| ---------- | -------- | -------- | ---------- | ----------------------------------------------- |
| `key`      | `string` | ✅        | —          | Destination column label.                       |
| `type`     | `string` | optional | `"string"` | Primitive hint (`string`, `number`, `date`, …). |
| `required` | `bool`   | optional | `false`    | If `true`, UI marks as mandatory.               |
| `notes`    | `string` | optional | —          | Shown as tooltip.                               |

---

### 3.2  `lookup`

> Second-pass mapping where a source value must match a controlled vocabulary (e.g., GL names → standard COA).

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

### 3.3  `computed`

> Derive a template column when not directly present in the client file.

```jsonc
{
  "type": "computed",
  "target_field": "NET_CHANGE",
  "formula": {
    "strategy": "first_available",
    "candidates": [
      {
        "type": "direct",
        "source_candidates": ["NET_CHANGE", "Change", "Monthly Change"]
      },
      {
        "type": "derived",
        "expression": "$END_BALANCE - $BEGIN_BALANCE",
        "dependencies": {
          "BEGIN_BALANCE": ["Beginning Balance", "Beg Bal"],
          "END_BALANCE":   ["Ending Balance",   "End Bal"]
        }
      }
    ]
  }
}
```

| Key            | Type     | Required | Notes                                |
| -------------- | -------- | -------- | ------------------------------------ |
| `target_field` | `string` | ✅        | Column created in the final dataset. |
| `formula`      | `object` | ✅        | See below.                           |

**Formula object**

| Key            | Type                            | Required    | Default             | Notes                                 |
| -------------- | ------------------------------- | ----------- | ------------------- | ------------------------------------- |
| `strategy`     | `"first_available" \| "always"` | ✅           | `"first_available"` | When to evaluate the expression.      |
| `candidates`   | `array<object>`                 | Conditional | —                   | Ordered tests for *direct* matches.   |
| `expression`   | `string`                        | Conditional | —                   | Arithmetic using `$PLACEHOLDERS`.     |
| `dependencies` | `object`                        | Conditional | —                   | Maps placeholders to header variants. |

---

## 4  Extending with new layer types

1. Define a **new Pydantic model** that inherits `BaseModel` in `schemas/template_v2.py`.
2. Add it to the `Layer` Union — e.g., `Layer = HeaderLayer | … | YourLayer`.
3. Implement a renderer/mapping helper in `app_utils.mapping.<your_layer>.py`.
4. Update UI to call the helper when `layer.type == "your_type"`.

No other files need modification.

---

## 5  Examples

### 5.1  PIT *BID* (header-only)

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

### 5.2  Standard COA (header + lookup + computed)

See `templates/coa_template.json`.

---

## 6  File-naming convention

* Save each template as **kebab-case**: `pit-bid.json`, `standard-coa.json`.
* The validator doesn’t care, but kebab-case improves CLI/URL readability.

---

## 7  Versioning & compatibility

* This spec is **v2**.
* The loader auto-detects legacy v1 templates (with `fields` + `accounts`) and **injects** equivalent `layers` at runtime, so old templates remain valid.
* Future specs will bump to v3 only if breaking changes are unavoidable.

---

## 8  Changelog

| Date       | Version | Change                                                 |
| ---------- | ------- | ------------------------------------------------------ |
| 2025-07-22 | 2.0     | Initial multilayer spec; removes mandatory `accounts`. |

```

---

### ✅ Roadmap update

| ID | Description | Status |
|----|-------------|--------|
| **A-3** | Draft `docs/template_spec.md` | **✔ complete** |

> **Next unlocked phase:** **B-1** – dynamic wizard (`build_steps(template_layers)` in `app_utils/ui_utils.py`).  
> When you’re ready, we can implement it or move on to any other task.
```
