"""Zuora workflow engine custom Liquid filters (Ruby ``Liquid::Filters``).

Used by ``lookup_workflow_reference(topic='liquid_custom_filters')``. Standard
Liquid filters may also exist; this document lists **Zuora-added** filters only.
Do not assume Shopify-style ``where`` arity — Zuora's ``where`` takes a property
name and a value to match.
"""

from __future__ import annotations

LIQUID_CUSTOM_FILTERS_REFERENCE = """## Zuora custom Liquid filters (workflows)

These filters extend the Liquid runtime in Zuora Workflow. Other stock Liquid
filters may be available; when in doubt, prefer the patterns below. Invalid
arguments raise Liquid syntax errors at runtime.

### Serialization and structure

- **`to_json`** — `{{ value | to_json }}` — JSON-encodes the value. **Fails** if the value is a Liquid Drop (use plain hashes, arrays, or scalars first).
- **`parse_json`** — `{{ json_string | parse_json }}` — Parses a JSON **string** into a Liquid-friendly structure. Fails on invalid JSON.
- **`string_escape`** — `{{ text | string_escape }}` — Ruby-style string escape for literals (input must be a String).
- **`to_xml`** — `{{ hash | to_xml }}` — Converts a **Hash** to XML. Non-hash input errors.

### Types and introspection

- **`data_type`** — `{{ value | data_type }}` — Ruby class name of the input.
- **`get_class`** — `{{ value | get_class }}` — Same idea as `data_type`.

### Geography and country

- **`us_state_name`** — `{{ value | us_state_name: 'full' }}` or `'abbreviation'` — Normalizes US state; invalid values error.
- **`canada_province_name`** — `{{ value | canada_province_name: 'full' }}` or `'abbreviation'` — Canadian provinces/territories.
- **`country_info`** — `{{ code_or_name | country_info: 'name' }}` — Second arg: `name`, `numeric`, `iso2`, `iso3`, `continent`, `iban`, `calling`, or `currency`. Resolves via ISO data; no exact match errors.

### Money and dates

- **`money`** — `{{ amount | money }}` or `{{ amount | money: 'USD' }}` — Without currency: `%.2f`. With currency: Money gem (string/number; NaN errors).
- **`date_manip`** — `{{ date | date_manip: '-', 5, 'day' }}` — Sign `'+'` or `'-'`, integer, metric: `minute`, `hour`, `day`, `week`, `month`, `year`.
- **`date_between`** — `{{ date | date_between: '2018-05-11', '2018-08-17' }}` — Boolean; start must be ≤ end.
- **`date_diff`** — `{{ date | date_diff: '2018-08-15' }}` — Absolute difference in whole days.
- **`timezone`** — `{{ input | timezone: previous_format, current_format, timezone_name }}` — `strptime` with first format, then `in_time_zone`, `strftime` second format.
- **`http_date`** — `{{ date | http_date }}` — RFC 1123 HTTP date.
- **`in_time_zone`** — `{{ 'now' | in_time_zone: 'America/Los_Angeles' }}` — Input: `now`, `today`, parseable string, or Time/Date. Unknown zone returns input unchanged.

### Text and regex

- **`regex`** — `{{ text | regex: '(([I][N][V])(.?)[0-9]{4,})', 'match_first' }}` or `'match_all'` — Input must be a String. `match_first`: first match captures; `match_all`: `scan` results.

### Collections (Zuora semantics)

- **`where`** — `{{ array_or_hash | where: 'Status', 'Posted' }}` — Filters hashes by property (string comparison). Hash input uses `.values`.
- **`where_exp`** — `{{ array | where_exp: 'item', 'item.Amount > 0' }}` — Variable name then Liquid comparison expression string.
- **`group_by`** — `{{ array | group_by: 'FieldName' }}` — Returns buckets `{ "name", "items", "size" }`.
- **`group_by_exp`** — `{{ array | group_by_exp: 'item', 'item.Type' }}` — Group key from rendered expression.
- **`pop` / `push` / `shift` / `unshift`** — `{{ array | pop }}`, `{{ array | pop: 2 }}`, `{{ array | push: elt }}`, `{{ array | shift }}`, `{{ array | unshift: elt }}` — Return new arrays (non-array passes through unchanged where noted in Ruby).

### Flash read/write

- **`flash_write`** — `{{ flash_id | flash_write: 'list', array }}` — `type`: `list`, `set`, or `hash`. For `list`/`set`, one array. For `hash`, two same-length arrays (keys zip values).
- **`flash_read`** — `{{ flash_id | flash_read: reference, 'default' }}` — Optional reference and read_command.

### Workflow and task introspection

- **`active_run_check_by_version`** — `{{ version_id | active_run_check_by_version }}` — True if any instance of that workflow **version** is Queued, Processing, or Pending.
- **`active_run_check_by_definition`** — `{{ definition_id | active_run_check_by_definition }}` — Same for a **definition** id.
- **`check_parent_workflow_status`** — `{{ id_or_name | check_parent_workflow_status: 'Finished' }}` — Status ∈ `Queued`, `Processing`, `Stopped`, `Stopping`, `Finished`. Integer = `original_workflow_id`; String = parent workflow **name**.
- **`check_processed_tag`** — `{{ tag | check_processed_tag: original_task_id }}` — True if a task with that `original_task_id` already has the tag.
- **`read_file`** — `{{ '' | read_file: task_id, file_tag }}` — First value ignored; reads file bytes from another task's Files output.

### Tenant / product

- **`is_ar_enabled`** — `{{ anything | is_ar_enabled }}` — Input ignored; tenant Invoice Settlement (AR) enabled flag.

### Random

- **`random`** — `{{ 0 | random: 2, 5 }}` — Inclusive integer range; bounds must be Integers (left input is conventional seed; see platform examples).
- **`random_variable`** — `{{ 0 | random_variable: 'uuid' }}` — Only `type` `'uuid'` is supported.

### Hashing and encoding

- **`md5`**, **`sha1`**, **`sha2`** — `{{ text | sha2: 'SHA256' }}` — `sha2` algorithm: `SHA256`, `SHA384`, or `SHA512` (default SHA512); hex digest.
- **`sha256_encode64`** — Base64(SHA256(binary)).
- **`base64_encode`** / **`base64_decode`** — Standard Base64 (encode strips newlines).

### HMAC and JWT

- **`hmac`** — `{{ data | hmac: 'SHA256', key }}` — OpenSSL HMAC hex digest.
- **`hmac_sha256_sign`** — Key is Base64-decoded; output Base64.
- **`hmac_sha256_hex`** — Plain string key; hex digest; normalizes CRLF in data.
- **`hmac_sha512_sign`** — Same as SHA256 sign with SHA512 and Base64 key.
- **`jwt_decode`** — `{{ token | jwt_decode: key, verify }}` — Boolean verify flag.
- **`jwt_encode`** — `{{ payload | jwt_encode: key, 'HS256' }}` — RS* algorithms accept PEM RSA key.

### RSA and AES

- **`rsa_decrypt`** — `{{ cipher_b64 | rsa_decrypt: private_key_pem }}`
- **`rsa_encrypt`** — `{{ data | rsa_encrypt: 'encrypt', pem }}` — Action `encrypt` or `decrypt`; string data per platform conventions.
- **`rsa_random_key`** — `{{ '' | rsa_random_key: mode }}` — OpenSSL cipher mode string (e.g. key-generation usage).
- **`aes_decrypt`** — `{{ cipher_b64 | aes_decrypt: iv_b64, key_b64, 'AES-256-CBC' }}` — Modes `AES-128-CBC` or `AES-256-CBC`.
- **`symmetric_encrypt`** — `{{ data | symmetric_encrypt: 'encrypt', mode, key_b64, iv_b64, true }}` — Optional IV; padding flag.

### Binary helpers

- **`input_byte_8x`**, **`utf_8_encoding`**, **`unpack`**, **`pack`** — Padding to 8-byte boundary, force UTF-8, hex unpack/pack.
"""
