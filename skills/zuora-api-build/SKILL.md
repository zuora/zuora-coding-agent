---
name: zuora-api-build
description: Generate or update Zuora integration code using the selected APIs
argument-hint: <language> <API or requirement description>
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash, Agent, mcp__zuora-mcp__zuora_codegen, mcp__zuora-mcp__ask_zuora, mcp__zuora-mcp__query_objects]
---

You are generating Zuora integration code. The user has either already run `/zuora-api-design` or is describing what they want to build.

## Input

The user's request: $ARGUMENTS

## Workflow

### Step 1: Determine language and scope

Identify the target language (Java, Python, Node.js, C#, curl). If not specified, ask the user. Understand what APIs and operations are needed.

### Step 2: Follow the mandatory codegen workflow

This sequence is critical — call `mcp__zuora-mcp__zuora_codegen` in this exact order:

1. **`code_guidance`** with the target language — get SDK setup instructions and workflow guidance. This MUST be called first.
2. **`list_api_classes`** — if the right API class is unclear, list all available classes to find the right one.
3. **`get_class_apis`** — for the relevant class(es), get all available API methods.
4. **`get_api_details`** — for each endpoint you will use, get method signature, parameters, request/response models.
5. **`get_model_details`** — for ALL request and response models you will use. This is mandatory to get actual field names, types, and enum values. Call this for each model class. For complex field types, recursively call `get_model_details(fieldTypeName)`.
6. **`code_rules`** — get language-specific coding rules. This MUST be called before presenting code to the user.

For simple queries (single API, known models), you may skip step 2 and go directly to step 3.

### Step 3: Generate code

Following the patterns from `code_guidance` and rules from `code_rules`:

- Include SDK client initialization and authentication setup
- Use correct model classes and constructors from `get_model_details` response
- Use actual enum values — never guess enum strings
- Include error handling (try/catch, HTTP status checks, retry logic)
- Include pagination handling for list/query operations
- Add comments mapping code to business requirements
- Follow language-specific conventions:
  - **Java**: Fluent builder pattern, `.execute()` calls, SDK enum constants
  - **Python**: Snake_case, keyword arguments, async/await where appropriate
  - **Node.js**: camelCase, async/await, property assignment
  - **C#**: PascalCase classes, camelCase methods, `Async` suffix on async methods
  - **curl**: Environment variables for credentials, proper header formatting

### Step 4: Read reference patterns

Read `${CLAUDE_PLUGIN_ROOT}/references/api-integration-patterns.md` and `${CLAUDE_PLUGIN_ROOT}/references/best-practices.md`. Apply relevant patterns to the generated code.

### Step 5: Write code to files

If the user's project context is clear (they're working in a repo), write code to appropriate files. Otherwise, present the code inline.

### Step 6: Suggest validation

Recommend the user run `/zuora-validate` on the generated code to check for correctness.

## Critical rules

- NEVER generate code before completing steps 2.1 through 2.6. The MCP responses contain actual SDK structure.
- NEVER guess field names or enum values — always use values from `get_model_details`.
- NEVER use setter methods like `setName()` in Java — use fluent builder pattern.
- For discriminated types in Java/C#: instantiate the specific subtype first, then wrap in the base request class.
- Always include proper error handling — at minimum, catch and log HTTP errors.
