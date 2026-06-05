# Zuora Workflow Liquid Filter Signatures

Source of truth: `~/Workspace/workflow/rails/lib/liquid/filters.rb`. Argument counts below exclude the piped input value on the left side of `|`.

Prefer these Workflow-specific filters when they express the operation. Use stock Liquid filters for common string/array work (`date`, `default`, `split`, `join`, `replace`, `first`, `last`, `size`, `upcase`, `downcase`, `strip`, etc.).

## Array And Grouping

| Filter | Piped input | Args | Returns | Example |
| ------ | ----------- | ---- | ------- | ------- |
| `where` | Array or Hash values | `property: String`, `value: any scalar` | Array of Hash rows whose `property` contains `value` after string coercion | `{% assign active = Data.Subscription | where: "Status", "Active" %}` |
| `where_exp` | Array or Hash values | `variable: String`, `expression: String Liquid comparison` | Array of rows where expression is true | `{% assign posted = Data.Invoice | where_exp: "inv", "inv.Status == 'Posted'" %}` |
| `group_by` | Enumerable | `property: String` or `Integer` for array rows | Array of `{name, items, size}` groups | `{% assign by_account = Data.Invoice | group_by: "AccountId" %}` |
| `group_by_exp` | Enumerable | `variable: String`, `expression: String Liquid expression` | Array of `{name, items, size}` groups | `{% assign by_month = Data.Invoice | group_by_exp: "inv", "inv.InvoiceDate | date: '%Y-%m'" %}` |
| `push` | Array | `input: any` | New array with item appended | `{% assign ids = ids | push: row.Id %}` |
| `pop` | Array | optional `num: Integer`, default `1` | New array with last `num` items removed | `{% assign trimmed = ids | pop: 2 %}` |
| `shift` | Array | optional `num: Integer`, default `1` | New array with first `num` items removed | `{% assign tail = ids | shift %}` |
| `unshift` | Array | `input: any` | New array with item prepended | `{% assign ids = ids | unshift: firstId %}` |

For simple filtering, prefer `where` / `where_exp` over `{% for %}` + `{% if %}` + `push`. Manual loops are fine when transforming rows or creating a shape these filters cannot express.

## Data Conversion And Formatting

| Filter | Piped input | Args | Returns | Example |
| ------ | ----------- | ---- | ------- | ------- |
| `to_json` | any non-Drop value | none | JSON string | `{{ payload | to_json }}` |
| `parse_json` | String | none | Parsed Hash/Array | `{% assign mapping = Data.Workflow.MappingJson | parse_json %}` |
| `to_xml` | Hash | none | XML string | `{{ payload | to_xml }}` |
| `string_escape` | String or nil | none | Escaped string | `{{ raw | string_escape }}` |
| `data_type` / `get_class` | any | none | Ruby class name string | `{{ Data.Invoice | data_type }}` |
| `money` | String, Integer, Float, or nil | optional `currency: String` | Formatted money string | `{{ Data.Invoice.Balance | money: Data.Account.Currency }}` |
| `regex` | String | `regexp: String`, `operation: "match_first"|"match_all"` | Match array | `{{ input | regex: "INV[0-9]+", "match_first" }}` |

## Dates And Timezones

| Filter | Piped input | Args | Returns | Example |
| ------ | ----------- | ---- | ------- | ------- |
| `date_manip` | Date-like value | `sign: "+"|"-"`, `number: Integer`, `metric: "minute"|"hour"|"day"|"week"|"month"|"year"` | Time | `{{ Data.Workflow.InvoiceDate | date_manip: "+", 1, "month" | date: "%Y-%m-%d" }}` |
| `date_between` | Date-like value | `start_date: Date-like`, `end_date: Date-like` | Boolean | `{{ Data.Workflow.ExecutionDate | date_between: "2026-01-01", "2026-12-31" }}` |
| `date_diff` | Date-like value | `date2: Date-like` | Absolute day difference Integer | `{{ Data.Invoice.DueDate | date_diff: Data.Workflow.ExecutionDate }}` |
| `timezone` | String | `previous_format: String`, `current_format: String`, `timezone: String` | Formatted time string | `{{ ts | timezone: "%Y-%m-%d", "%F %T", "UTC" }}` |
| `in_time_zone` | `"now"`, `"today"`, String, Time, or Date | `timezone: IANA timezone String` | Time or original input if invalid | `{{ "now" | in_time_zone: "America/New_York" | date: "%Y-%m-%d" }}` |
| `http_date` | Date-like value | none | HTTP date string | `{{ "now" | http_date }}` |

## Geography

| Filter | Piped input | Args | Returns | Example |
| ------ | ----------- | ---- | ------- | ------- |
| `us_state_name` | State name or abbreviation String | `form: "full"|"abbreviation"` | Converted state string | `{{ "CA" | us_state_name: "full" }}` |
| `canada_province_name` | Province name or abbreviation String | `form: "full"|"abbreviation"` | Converted province string | `{{ "ON" | canada_province_name: "full" }}` |
| `country_info` | Country/currency/name String | `action: "name"|"numeric"|"iso2"|"iso3"|"continent"|"iban"|"calling"|"currency"` | Requested country metadata | `{{ "United States" | country_info: "iso2" }}` |

## Encoding, Hashing, Signing

| Filter | Piped input | Args | Returns | Example |
| ------ | ----------- | ---- | ------- | ------- |
| `base64_encode` / `base64_decode` | String | none | Encoded/decoded String | `{{ raw | base64_encode }}` |
| `md5` / `sha1` | String | none | Hex digest String | `{{ raw | sha1 }}` |
| `sha2` | String | optional `algorithm: "SHA256"|"SHA384"|"SHA512"`, default `"SHA512"` | Hex digest String | `{{ raw | sha2: "SHA256" }}` |
| `sha256_encode64` | String | none | Base64 SHA256 digest | `{{ raw | sha256_encode64 }}` |
| `hmac` | String data | `digest: String`, `key: String` | Hex digest String | `{{ raw | hmac: "sha256", secret }}` |
| `hmac_sha256_sign` | String | `key: Base64 String` | Base64 signature String | `{{ raw | hmac_sha256_sign: key }}` |
| `hmac_sha256_hex` | String | `key: String` | Hex signature String | `{{ raw | hmac_sha256_hex: key }}` |
| `hmac_sha512_sign` | String | `key: Base64 String` | Base64 signature String | `{{ raw | hmac_sha512_sign: key }}` |
| `rsa_encrypt` | Base64 String | `action: "encrypt"|"decrypt"`, `key: PEM String` | Base64 String | `{{ raw | rsa_encrypt: "encrypt", publicKey }}` |
| `rsa_decrypt` | Base64 String | `private_key: PEM String` | Base64 String | `{{ encrypted | rsa_decrypt: privateKey }}` |
| `aes_decrypt` | Base64 String | `decryption_IV: Base64 String`, `decryption_key: Base64 String`, `mode: "AES-128-CBC"|"AES-256-CBC"` | String | `{{ encrypted | aes_decrypt: iv, key, "AES-256-CBC" }}` |
| `symmetric_encrypt` | String | `action: "encrypt"|"decrypt"`, `mode: String`, `key: Base64 String`, optional `iv: Base64 String`, optional `no_padding: Boolean-like`, default `true` | String bytes | `{{ raw | symmetric_encrypt: "encrypt", "AES-256-CBC", key, iv }}` |
| `rsa_random_key` | any | `mode: String cipher mode` | Random key bytes | `{{ "" | rsa_random_key: "AES-256-CBC" }}` |
| `jwt_encode` / `jwt_decode` | Payload Hash or token String | encode: `key: String`, `algorithm: String`; decode: `key: String`, `verify: Boolean` | JWT String or decoded Array | `{{ payload | jwt_encode: key, "HS256" }}` |
| `input_byte_8x` / `utf_8_encoding` / `unpack` / `pack` | String | none | Padded/encoded/hex-packed String | `{{ raw | utf_8_encoding }}` |

## Workflow Runtime Helpers

Use these only when the workflow genuinely needs runtime introspection or file access.

| Filter | Piped input | Args | Returns | Example |
| ------ | ----------- | ---- | ------- | ------- |
| `active_run_check_by_version` | Workflow version id | none | Boolean | `{{ WorkflowSetup.id | active_run_check_by_version }}` |
| `active_run_check_by_definition` | Workflow definition id | none | Boolean | `{{ WorkflowSetup.workflow_definition_id | active_run_check_by_definition }}` |
| `check_parent_workflow_status` | Parent workflow id Integer or name String | `status: "Queued"|"Processing"|"Stopped"|"Stopping"|"Finished"` | Boolean | `{{ WorkflowSetup.name | check_parent_workflow_status: "Processing" }}` |
| `check_processed_tag` | Tag String | `original_task_id: Integer/String` | Boolean | `{{ "tag-name" | check_processed_tag: TaskInstance.id }}` |
| `read_file` | ignored | `task_id: Integer/String`, `file_tag: String` | File contents String | `{{ "" | read_file: 123, "MyFile.csv" }}` |
| `is_ar_enabled` | ignored | none | Boolean | `{{ "" | is_ar_enabled }}` |
| `random` | any | `from: Integer`, `to: Integer` | Random Integer | `{{ "" | random: 1, 10 }}` |
| `random_variable` | any | `type: "uuid"` | UUID String | `{{ "" | random_variable: "uuid" }}` |
