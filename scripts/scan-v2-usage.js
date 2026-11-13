#!/usr/bin/env node

/**
 * scan-v2-usage.js — Deterministic, dependency-free v2 API usage scanner.
 *
 * Detects Zuora v2 API call sites in a customer codebase and emits a
 * structured v2-inventory.json.
 *
 * Usage:
 *   node scan-v2-usage.js <codebase-path> [--patterns <file>] [--out <file>] [--context-lines N]
 *
 * Exit codes: 0 = success (even with zero sites), 2 = usage error or unreadable path.
 * Output is deterministic (sorted by file, line, column).
 * Without --out, inventory JSON goes to stdout; progress and warnings go to stderr.
 *
 * Exports: scanDirectory, scanText, redact, loadPatterns, deriveSdkNames (for tests).
 *
 * Java SDK matching (B73):
 *   - Accessor-chain: .<accessor>().<method>( e.g. client.accounts().getAccounts(
 *   - Multi-line accessor-chain: continuation line starting with .<method>( where the
 *     previous non-blank non-comment line (up to 3 back) ends with .<accessor>() is matched;
 *     the site is reported on the method-call line.
 *   - Typed-variable: AccountsApi api = client.accounts(); api.getAccounts(
 *   - Multi-line typed-variable: variable on one line, .method( on next continuation line.
 *   - v2 context required: file imports com.zuora.sdk.ZuoraClient or org.openapitools.client.
 *     or contains quickStartApi(
 *   - billingDocuments().get( and accountsApi() etc are NOT v2 and never reported
 *   - new ZuoraClient( is classified by imports: only a direct-v2-client construction risk
 *     when the file imports com.zuora.sdk.ZuoraClient (not just com.zuora.ZuoraClient).
 *
 * Derived SDK match notes:
 *   - Derived detection is controlled by detect_from_operation_id flag in patterns file.
 *     When false (default), only Java exact matching is used; other languages are URL-only.
 *   - When derive_from_operation_id is true, deriveSdkNames is used for all supported
 *     languages to match SDK method names.
 *   - A derived SDK match takes the whole line (one site per line). If a line contains both
 *     a URL regex match and a derived SDK name, the derived match wins (score = pathLen+1000
 *     vs pathLen for URL). Downstream consumers that need URL-based precision should filter
 *     sites with notes: ["sdk_method_derived_from_operation_id"].
 *   - Block comments spanning multiple lines are not recognized: the scanner reads one line
 *     at a time. A derived name on a line that is the continuation of a block comment (not
 *     the opening line) will still be matched if the file has SDK context.
 *
 * Known limitations:
 *   - JAVA_ACCESSOR_TO_API_CLASS and detection-patterns.json must both be updated when a
 *     new v2 API class (pack) is added to the Java SDK.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const os = require("os");

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SCANNER_VERSION = "1.0";
const MAX_FILE_SIZE = 1024 * 1024; // 1 MiB
const BINARY_CHECK_BYTES = 8192;
const MAX_LINE_LENGTH = 2000;
const MAX_SITES = 5000;
const MAX_FILES = 50000;
const DEFAULT_CONTEXT_LINES = 3;

const SKIP_DIRS = new Set([
  ".git", "node_modules", "vendor", "dist", "build",
  "target", "out", ".venv", "venv", "__pycache__",
  ".idea", ".vscode",
]);

const LANGUAGE_MAP = {
  java: "java",
  js: "javascript", jsx: "javascript",
  ts: "javascript", tsx: "javascript",
  mjs: "javascript", cjs: "javascript",
  py: "python",
  cs: "csharp",
  go: "go",
  rb: "ruby",
  php: "php",
  sh: "shell", bash: "shell", zsh: "shell",
};

// ---------------------------------------------------------------------------
// SDK context patterns — a file must contain at least one of these to trigger
// derived SDK method detection (prevents false positives from generic names).
// ---------------------------------------------------------------------------

const SDK_CONTEXT_PATTERNS = [
  // Java / Kotlin — import com.zuora.<anything>
  /\bimport\s+com\.zuora\b/,
  // Java — new ZuoraClient( (also covered by generic entry below)
  // C# — using Zuora; / using Zuora.Api; / using Zuora.Client;
  /\busing\s+Zuora\b/,
  // Python — bare: import zuora, import zuora as z
  //           sub-pkg: import zuora_sdk, import zuora.api
  //           from: from zuora import X, from zuora.api import X, from zuora_sdk import X
  // Word boundary after "zuora" prevents matching "zuorafoo" or "mozuora".
  /\bimport\s+zuora\b/i,
  /\bfrom\s+zuora\b/i,
  // JavaScript / TypeScript — require('zuora'), require("@zuora/..."), import from 'zuora'
  /require\s*\(\s*['"]zuora/i,
  /@zuora\//,
  /from\s+['"]zuora/i,
  /zuora[_\-]sdk/i,
  // Go — "github.com/zuora/..." in import block
  /github\.com\/zuora/i,
  // Ruby — require 'zuora', require "zuora/...", Zuora::
  /Zuora::/,
  /require\s*['"]zuora/i,
  // PHP — use Zuora\...; / new \Zuora\... / Zuora\ namespace usage
  /use\s+Zuora\\/i,
  /\\Zuora\\/,
  /include\s*['"]zuora/i,
  // Generic client constructors (any language)
  /\bZuoraClient\b/,
  /\bzuora_client\b/,
];

// ---------------------------------------------------------------------------
// Java v2 SDK context patterns
// A Java file is considered to have v2 SDK context if it:
//   (a) imports com.zuora.sdk.ZuoraClient (direct v2 client)
//   (b) uses org.openapitools.client. (v2 API class FQN)
//   (c) calls quickStartApi( (unified client path to v2)
// ---------------------------------------------------------------------------
const JAVA_V2_SDK_CONTEXT_RE = [
  /\bimport\s+com\.zuora\.sdk\b/,                 // com.zuora.sdk.ZuoraClient import
  /\bcom\.zuora\.sdk\.ZuoraClient\b/,              // fully-qualified usage
  /\bimport\s+org\.openapitools\.client\b/,        // v2 API class import
  /\borg\.openapitools\.client\b/,                 // FQN usage
  /\bquickStartApi\s*\(/,                           // unified client accessor
];

// ---------------------------------------------------------------------------
// Java v2 API class names (without the "Api" suffix in the accessor)
// and their corresponding API class types (for typed-variable detection).
// Keys are accessor names (no suffix), values list their API class type names.
// ---------------------------------------------------------------------------
const JAVA_ACCESSOR_TO_API_CLASS = {
  accounts:         ["AccountsApi"],
  invoices:         ["InvoicesApi"],
  invoiceItems:     ["InvoiceItemsApi"],
  billingDocuments: ["BillingDocumentsApi"],
  subscriptions:    ["SubscriptionsApi"],
};

// Build reverse map: api class -> accessor name
const JAVA_API_CLASS_TO_ACCESSOR = {};
for (const [acc, classes] of Object.entries(JAVA_ACCESSOR_TO_API_CLASS)) {
  for (const cls of classes) {
    JAVA_API_CLASS_TO_ACCESSOR[cls] = acc;
  }
}

// ---------------------------------------------------------------------------
// deriveSdkNames — derive SDK method name spellings for a given operationId
// ---------------------------------------------------------------------------

/**
 * Derive the accepted SDK method name spellings for a given operationId and language.
 *
 * Naming conventions:
 *   java, javascript/typescript, php: camelCase as given (getAccounts)
 *   python, ruby: snake_case (get_accounts)
 *   csharp: PascalCase (GetAccounts) + async form (GetAccountsAsync)
 *   go: PascalCase (GetAccounts)
 *
 * Additional suffix variants:
 *   java: ...WithHttpInfo, ...Async
 *
 * @param {string} operationId - e.g. "getAccounts"
 * @param {string} language    - one of java, javascript, python, csharp, go, ruby, php
 * @returns {string[]} list of accepted method name strings (without parens)
 */
function deriveSdkNames(operationId, language) {
  if (!operationId || typeof operationId !== "string") return [];

  // Helper: camelCase → snake_case
  function toSnakeCase(s) {
    return s
      .replace(/([A-Z])/g, "_$1")
      .replace(/^_/, "")
      .toLowerCase();
  }

  // Helper: camelCase → PascalCase
  function toPascalCase(s) {
    return s.charAt(0).toUpperCase() + s.slice(1);
  }

  const camel = operationId; // already camelCase from operationId
  const pascal = toPascalCase(camel);
  const snake = toSnakeCase(camel);

  switch (language) {
    case "java":
      return [camel, camel + "WithHttpInfo", camel + "Async"];
    case "javascript":
      return [camel];
    case "python":
      return [snake];
    case "csharp":
      return [pascal, pascal + "Async"];
    case "go":
      return [pascal];
    case "ruby":
      return [snake];
    case "php":
      return [camel];
    default:
      return [];
  }
}

// Patterns for detecting HTTP methods near a match
const HTTP_METHOD_HINTS = [
  { re: /\.get\s*\(/i, method: "GET" },
  { re: /\.post\s*\(/i, method: "POST" },
  { re: /\.put\s*\(/i, method: "PUT" },
  { re: /\.patch\s*\(/i, method: "PATCH" },
  { re: /\.delete\s*\(/i, method: "DELETE" },
  { re: /axios\.get\b/i, method: "GET" },
  { re: /axios\.post\b/i, method: "POST" },
  { re: /axios\.put\b/i, method: "PUT" },
  { re: /axios\.patch\b/i, method: "PATCH" },
  { re: /axios\.delete\b/i, method: "DELETE" },
  { re: /requests\.get\b/i, method: "GET" },
  { re: /requests\.post\b/i, method: "POST" },
  { re: /requests\.put\b/i, method: "PUT" },
  { re: /requests\.patch\b/i, method: "PATCH" },
  { re: /requests\.delete\b/i, method: "DELETE" },
  { re: /HttpMethod\.GET\b/i, method: "GET" },
  { re: /HttpMethod\.POST\b/i, method: "POST" },
  { re: /HttpMethod\.PUT\b/i, method: "PUT" },
  { re: /HttpMethod\.PATCH\b/i, method: "PATCH" },
  { re: /HttpMethod\.DELETE\b/i, method: "DELETE" },
  { re: /-X\s+GET\b/i, method: "GET" },
  { re: /-X\s+POST\b/i, method: "POST" },
  { re: /-X\s+PUT\b/i, method: "PUT" },
  { re: /-X\s+PATCH\b/i, method: "PATCH" },
  { re: /-X\s+DELETE\b/i, method: "DELETE" },
  { re: /method\s*:\s*['"]GET['"]/i, method: "GET" },
  { re: /method\s*:\s*['"]POST['"]/i, method: "POST" },
  { re: /method\s*:\s*['"]PUT['"]/i, method: "PUT" },
  { re: /method\s*:\s*['"]PATCH['"]/i, method: "PATCH" },
  { re: /method\s*:\s*['"]DELETE['"]/i, method: "DELETE" },
  { re: /\.sendGet\b/i, method: "GET" },
  { re: /\.sendPost\b/i, method: "POST" },
  { re: /HttpGet\b/, method: "GET" },
  { re: /HttpPost\b/, method: "POST" },
  { re: /HttpPut\b/, method: "PUT" },
  { re: /HttpPatch\b/, method: "PATCH" },
  { re: /HttpDelete\b/, method: "DELETE" },
  { re: /GetAsync\b/, method: "GET" },
  { re: /PostAsync\b/, method: "POST" },
  { re: /PutAsync\b/, method: "PUT" },
  { re: /PatchAsync\b/, method: "PATCH" },
  { re: /DeleteAsync\b/, method: "DELETE" },
];

// Patterns for base_url_variable risk
const BASE_URL_VAR_RE = /\$\{[^}]+\}\/|[A-Za-z_][A-Za-z0-9_]*\s*\+\s*["'`]\/(?:v2\/)?[a-z]/;

// Dynamic URL concatenation risk (v2 prefix built by concat)
const DYNAMIC_URL_RE = /["'`]\s*\+\s*["'`]\/v2\b|\/v2["'`]\s*\+/;

// wrapper_idiom stable fragments
const WRAPPER_IDIOM_JAVA = /new\s+ZuoraClient\s*\(/;
const WRAPPER_IDIOM_JS = /new\s+ZuoraClient\s*\(\s*\{/;

// Java v2 direct client construction (com.zuora.sdk)
// Match: new ZuoraClient( or new com.zuora.sdk.ZuoraClient(
const JAVA_V2_DIRECT_CLIENT_RE = /\bnew\s+(?:com\.zuora\.sdk\.)?ZuoraClient\s*\(/;

// Java unified client quickStartApi accessor
const JAVA_QUICKSTART_RE = /\bquickStartApi\s*\(/;

// Java unified v1 client construction (com.zuora.ZuoraClient — NOT the v2 sdk)
const JAVA_V1_UNIFIED_CLIENT_RE = /\bnew\s+com\.zuora\.ZuoraClient\s*\(/;

// ---------------------------------------------------------------------------
// loadPatterns
// ---------------------------------------------------------------------------

/**
 * Load and compile detection patterns from a JSON file.
 * Returns { entries, compiledEntries, pathPrefix, wrapperIdioms, sdkDetection,
 *           javaAccessorChains, javaTypedVarPatterns, deriveFromOperationId }
 */
function loadPatterns(patternsFile) {
  const raw = JSON.parse(fs.readFileSync(patternsFile, "utf8"));
  const pathPrefix = raw.base_url_hints && raw.base_url_hints.path_prefix
    ? raw.base_url_hints.path_prefix
    : "/v2";

  // Read sdk_detection top-level config
  const sdkDetectionConfig = raw.sdk_detection || {};
  const deriveFromOperationId = sdkDetectionConfig.derive_from_operation_id === true;

  // Derived SDK languages: languages that deriveSdkNames supports
  const DERIVED_LANGUAGES = ["java", "javascript", "python", "csharp", "go", "ruby", "php"];

  // Languages that get derived matching (only when derive_from_operation_id is true)
  const activeDeriveLangs = deriveFromOperationId ? DERIVED_LANGUAGES : [];

  const compiledEntries = (raw.entries || []).map((entry) => {
    const flags = entry.url_regex_flags || "";
    let compiledRe = null;
    try {
      compiledRe = new RegExp(entry.url_regex, flags);
    } catch (e) {
      // skip invalid
    }
    // Compile explicit SDK method patterns per language.
    // For Java: we use the new accessor-chain and typed-variable matching instead of
    // the old string fragment approach. sdkPatterns is not used for Java anymore.
    const sdkPatterns = {};
    for (const [lang, sdkObj] of Object.entries(entry.sdk_methods || {})) {
      if (lang === "java") continue; // Java uses new exact matching
      const method = sdkObj && sdkObj.method;
      if (!method || method === "UNKNOWN") continue;
      // Extract stable fragment from the method signature.
      // e.g. "zuoraClient.accounts().getAccounts(...)" -> "zuoraClient.accounts().getAccounts("
      // We find the last "(" and keep everything up to and including it.
      // This ensures getAccount( doesn't match getAccounts( etc.
      const lastParen = method.lastIndexOf("(");
      const fragment = lastParen >= 0 ? method.slice(0, lastParen + 1) : method;
      // Escape special regex chars
      const escaped = fragment.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      try {
        sdkPatterns[lang] = new RegExp(escaped);
      } catch (_) { /* skip */ }
    }

    // Compile derived SDK method patterns for supported languages (only if enabled).
    const derivedSdkPatterns = {};
    if (entry.operationId && activeDeriveLangs.length > 0) {
      for (const lang of activeDeriveLangs) {
        const names = deriveSdkNames(entry.operationId, lang);
        if (names.length === 0) continue;
        // Build a regex that matches any of the derived names as a call site.
        // Sort by length descending for longest-match priority within a language.
        const sortedNames = names.slice().sort((a, b) => b.length - a.length);
        const alts = sortedNames.map((n) => n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
        // (?<![A-Za-z0-9_]) ensures we don't match inside longer identifiers
        // \s* allows optional whitespace before the opening paren
        const reSrc = `(?<![A-Za-z0-9_])(${alts.join("|")})\\s*\\(`;
        try {
          derivedSdkPatterns[lang] = new RegExp(reSrc);
        } catch (_) { /* skip */ }
      }
    }

    return { ...entry, compiledRe, sdkPatterns, derivedSdkPatterns };
  });

  // Build Java accessor-chain patterns for each entry that has java sdk_methods.
  // For each entry with java.accessor and java.methods, build:
  //   1. Accessor-chain regex: \.<accessor>\(\s*\)\s*\.<method>\s*\(
  //      Allows whitespace/newline between the two method calls.
  //   2. Typed-variable patterns: for each API class, varName.<method>(
  // These are separate from the old sdkPatterns mechanism.
  const javaAccessorChains = []; // { entry, accessorRe, methodName, cardId }
  const javaTypedVarInfo = []; // { entry, apiClass, methods, cardId }

  for (const entry of (raw.entries || [])) {
    const javaSdk = entry.sdk_methods && entry.sdk_methods.java;
    if (!javaSdk) continue;
    const accessor = javaSdk.accessor;
    const methods = javaSdk.methods;
    if (!accessor || !Array.isArray(methods) || methods.length === 0) continue;

    const accessorEsc = accessor.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const apiClasses = JAVA_ACCESSOR_TO_API_CLASS[accessor] || [];

    for (const methodName of methods) {
      // Accessor-chain: .<accessor>(...).<method>(
      // We match: .<accessor>() optionally followed by whitespace then .<method>(
      // The 'get' alias is special: we only match it for entries that include it.
      const methodEsc = methodName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      let reSrc;
      if (methodName === "get") {
        // The generic alias: .<accessor>().get(
        // We match dot + accessor + () + optional whitespace + .get(
        // This excludes xxxApi() accessors (those end in Api)
        reSrc = `\\.${accessorEsc}\\s*\\(\\s*\\)\\s*\\.get\\s*\\(`;
      } else {
        reSrc = `\\.${accessorEsc}\\s*\\(\\s*\\)\\s*\\.${methodEsc}\\s*\\(`;
      }
      let compiledChainRe;
      try {
        compiledChainRe = new RegExp(reSrc);
      } catch (_) { continue; }

      javaAccessorChains.push({
        entry,
        accessorName: accessor,
        methodName,
        compiledChainRe,
      });
    }

    // Typed-variable info (we store the list of methods per API class, resolved at file level)
    if (apiClasses.length > 0) {
      javaTypedVarInfo.push({
        entry,
        accessor,
        apiClasses,
        methods,
      });
    }
  }

  // Build sdk_detection summary using the new model:
  //   explicit: languages with exact Java accessor+method detection (always "java" if java entries exist)
  //   derived: languages enabled via derive_from_operation_id (empty when false)
  const explicitLangs = new Set();
  for (const entry of (raw.entries || [])) {
    const javaSdk = entry.sdk_methods && entry.sdk_methods.java;
    if (javaSdk && javaSdk.accessor && Array.isArray(javaSdk.methods)) {
      explicitLangs.add("java");
    }
  }

  // Also collect any non-java explicit lang patterns (for forward compat)
  for (const entry of (raw.entries || [])) {
    for (const [lang, sdkObj] of Object.entries(entry.sdk_methods || {})) {
      if (lang === "java") continue;
      if (sdkObj && sdkObj.method && sdkObj.method !== "UNKNOWN") {
        explicitLangs.add(lang);
      }
    }
  }

  // derived: empty unless derive_from_operation_id is true
  const derivedLangs = deriveFromOperationId ? [...DERIVED_LANGUAGES].sort() : [];

  const sdkDetection = {
    explicit: [...explicitLangs].sort(),
    derived: derivedLangs,
  };

  // languages_without_sdk_pattern: scanner languages that have neither explicit nor derived detection
  // For B73: all non-java scanner languages (csharp, go, javascript, php, python, ruby) are URL-only
  const ALL_SCANNER_LANGS = ["csharp", "go", "javascript", "php", "python", "ruby"];
  const langsWithSdk = new Set([...sdkDetection.explicit, ...sdkDetection.derived]);
  const langsWithoutSdkPattern = ALL_SCANNER_LANGS.filter((l) => !langsWithSdk.has(l));

  return {
    raw,
    entries: raw.entries || [],
    compiledEntries,
    pathPrefix,
    wrapperIdioms: raw.wrapper_idioms || [],
    sdkDetection,
    javaAccessorChains,
    javaTypedVarInfo,
    deriveFromOperationId,
    langsWithoutSdkPattern,
  };
}

// ---------------------------------------------------------------------------
// Java v2 SDK context detection
// ---------------------------------------------------------------------------

/**
 * Check if a Java file has v2 SDK context (imports com.zuora.sdk or uses quickStartApi).
 */
function hasJavaV2SdkContext(text) {
  return JAVA_V2_SDK_CONTEXT_RE.some((re) => re.test(text));
}

/**
 * Extract typed API variable declarations from a Java file.
 * Looks for patterns like:
 *   AccountsApi accountsApi = ...;
 *   AccountsApi api = client.accounts();
 *   org.openapitools.client.api.AccountsApi someVar = ...;
 * Returns a map: varName -> accessor name
 */
function extractJavaTypedVars(text, javaTypedVarInfo) {
  const varToAccessor = {};

  // Build a set of known API class names
  const knownApiClasses = new Set(Object.keys(JAVA_API_CLASS_TO_ACCESSOR));

  // Match declarations like: AccountsApi varName = ...
  // Also match: org.openapitools.client.api.AccountsApi varName = ...
  for (const cls of knownApiClasses) {
    const clsEsc = cls.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // Simple FQN prefix or bare class name
    const declRe = new RegExp(
      `(?:org\\.openapitools\\.client\\.api\\.)?${clsEsc}\\s+([A-Za-z_][A-Za-z0-9_]*)\\s*=`,
      "g"
    );
    let m;
    while ((m = declRe.exec(text)) !== null) {
      const varName = m[1];
      if (varName && !varToAccessor[varName]) {
        varToAccessor[varName] = JAVA_API_CLASS_TO_ACCESSOR[cls];
      }
    }
  }

  return varToAccessor;
}

// ---------------------------------------------------------------------------
// Java multi-line accessor chain helpers
// ---------------------------------------------------------------------------

/**
 * Return true if a trimmed line is a Java single-line comment or blank.
 * Used when scanning prior lines for multi-line chain context.
 */
function isJavaCommentOrBlankLine(trimmed) {
  return trimmed === "" ||
    trimmed.startsWith("//") ||
    trimmed.startsWith("*") ||
    trimmed.startsWith("/*");
}

/**
 * Given an array of source lines and the index of the current line,
 * return the previous non-blank non-comment lines (up to maxLook back),
 * in order from closest to furthest. At most maxLook lines are returned.
 */
function prevNonBlankLines(lines, currentIdx, maxLook) {
  const result = [];
  for (let j = currentIdx - 1; j >= 0 && result.length < maxLook; j--) {
    const t = lines[j].trimStart();
    if (isJavaCommentOrBlankLine(t)) continue;
    // A line that ends a statement or block (";", "{", "}") cannot be continued by the current line:
    // stop here so a later ".get(" cannot bind to an accessor of an earlier, completed statement.
    // Strip a trailing // comment first so "client.accounts() // list" still ends with the accessor call.
    const code = stripTrailingComment(lines[j], "java");
    const end = code.trimEnd();
    if (end.endsWith(";") || end.endsWith("{") || end.endsWith("}")) break;
    result.push(code);
  }
  return result;
}

// Regex to test if a line ends with .<accessor>() (allowing trailing whitespace/semicolons)
// We build these lazily per accessor name.
const ACCESSOR_TAIL_RE_CACHE = {};
function getAccessorTailRe(accessorName) {
  if (!ACCESSOR_TAIL_RE_CACHE[accessorName]) {
    const esc = accessorName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // Line ends with .<accessor>() optionally followed by whitespace or line-continuation chars
    // We allow the chain to end with just .<accessor>() or .<accessor>() trailed by space/;
    ACCESSOR_TAIL_RE_CACHE[accessorName] = new RegExp(`\\.${esc}\\s*\\(\\s*\\)\\s*$`);
  }
  return ACCESSOR_TAIL_RE_CACHE[accessorName];
}

// Regex to test if a line starts with .<method>( (allowing leading whitespace)
// Returns the matched method name if found, or null.
function matchesMethodContinuation(trimmedLine) {
  // Matches .<identifier>( at the start of the trimmed line
  const m = /^\.([A-Za-z_][A-Za-z0-9_]*)\s*\(/.exec(trimmedLine);
  return m ? m[1] : null;
}

// ---------------------------------------------------------------------------
// Java v2 SDK match for a single line
// ---------------------------------------------------------------------------

/**
 * Try to match a Java line against accessor-chain and typed-variable patterns.
 * Also handles multi-line accessor chains and multi-line typed-variable calls.
 *
 * Returns best match or null.
 * Guards:
 *   - Never match xxxApi() accessors (v1 unified client methods like accountsApi())
 *   - billingDocuments().get( is not one of the nine operations
 *   - Comment lines are not matched
 *   - Only fires when hasJavaV2Context is true
 *
 * @param {string} line - source line (current)
 * @param {Object[]} javaAccessorChains - from loadPatterns
 * @param {Object} varToAccessor - map of varName -> accessor from typed declarations
 * @param {Object[]} javaTypedVarInfo - from loadPatterns
 * @param {boolean} hasJavaV2Context - file has v2 SDK context
 * @param {string[]} prevLines - previous non-blank non-comment lines (closest first),
 *                               used for multi-line chain detection
 * @returns {Object|null} { entry, matchedText, matchIndex, evidence, derived }
 */
function matchJavaLine(line, javaAccessorChains, varToAccessor, javaTypedVarInfo, hasJavaV2Context, prevLines) {
  if (!hasJavaV2Context) return null;
  if (line.length > MAX_LINE_LENGTH) return null;

  // Skip full-line comments
  const trimmed = line.trimStart();
  if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*")) {
    return null;
  }

  // prevLines defaults to empty array if not supplied
  if (!prevLines) prevLines = [];

  let bestMatch = null;
  let bestScore = -1;

  // --- Accessor-chain matching (single-line) ---
  for (const chain of javaAccessorChains) {
    const m = chain.compiledChainRe.exec(line);
    if (m) {
      // Guard: billingDocuments().get( is not one of the nine
      if (chain.accessorName === "billingDocuments" && chain.methodName === "get") {
        continue;
      }
      const pathLen = chain.entry.path ? chain.entry.path.length : 0;
      const score = pathLen + 2000;
      if (score > bestScore) {
        bestScore = score;
        bestMatch = {
          entry: chain.entry,
          matchedText: m[0],
          matchIndex: m.index,
          evidence: "sdk_method",
          derived: false,
        };
      }
    }
  }

  // --- Multi-line accessor-chain matching ---
  // Pattern: current line (trimmed) starts with .<method>( and one of the previous
  // non-blank non-comment lines (up to 3 back) ends with .<accessor>()
  // We report the site on the current (method-call) line.
  const continuationMethod = matchesMethodContinuation(trimmed);
  if (continuationMethod && prevLines.length > 0) {
    for (const chain of javaAccessorChains) {
      if (chain.methodName !== continuationMethod) continue;
      // Guard: billingDocuments + get excluded
      if (chain.accessorName === "billingDocuments" && chain.methodName === "get") continue;

      const tailRe = getAccessorTailRe(chain.accessorName);
      for (const prevLine of prevLines) {
        if (tailRe.test(prevLine)) {
          // Confirmed multi-line chain: .<accessor>() on a prior line, .<method>( on this line
          const pathLen = chain.entry.path ? chain.entry.path.length : 0;
          const score = pathLen + 2000;
          if (score > bestScore) {
            bestScore = score;
            // matchedText includes the accessor from the prev line + method from current
            const prevTrimmed = prevLine.trimStart();
            const accessorMatch = new RegExp(`\\.${chain.accessorName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\(\\s*\\)`).exec(prevTrimmed);
            const accessorPart = accessorMatch ? accessorMatch[0] : "." + chain.accessorName + "()";
            const methodMatch = /^\.[A-Za-z_][A-Za-z0-9_]*\s*\(/.exec(trimmed);
            const methodPart = methodMatch ? methodMatch[0] : "." + continuationMethod + "(";
            bestMatch = {
              entry: chain.entry,
              matchedText: accessorPart + methodPart,
              matchIndex: 0,
              evidence: "sdk_method",
              derived: false,
            };
          }
          break; // found the accessor line
        }
      }
    }
  }

  // --- Typed-variable matching (single-line and multi-line) ---
  if (Object.keys(varToAccessor).length > 0) {
    for (const [varName, accessorName] of Object.entries(varToAccessor)) {
      for (const tvInfo of javaTypedVarInfo) {
        if (tvInfo.accessor !== accessorName) continue;

        for (const methodName of tvInfo.methods) {
          // Guard: billingDocuments typed var + get is not one of the nine
          if (accessorName === "billingDocuments" && methodName === "get") continue;

          const varEsc = varName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
          const methodEsc = methodName.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

          // Single-line: varName.method(
          let reSrc;
          if (methodName === "get") {
            reSrc = `\\b${varEsc}\\s*\\.\\s*get\\s*\\(`;
          } else {
            reSrc = `\\b${varEsc}\\s*\\.\\s*${methodEsc}\\s*\\(`;
          }
          let re;
          try { re = new RegExp(reSrc); } catch (_) { continue; }
          const m = re.exec(line);
          if (m) {
            const isDecl = new RegExp(
              `\\b(?:org\\.openapitools\\.client\\.api\\.)?(?:${Object.keys(JAVA_API_CLASS_TO_ACCESSOR).join("|")})\\s+${varEsc}\\s*=`
            ).test(line);
            if (!isDecl) {
              const pathLen = tvInfo.entry.path ? tvInfo.entry.path.length : 0;
              const score = pathLen + 2000;
              if (score > bestScore) {
                bestScore = score;
                bestMatch = {
                  entry: tvInfo.entry,
                  matchedText: m[0],
                  matchIndex: m.index,
                  evidence: "sdk_method",
                  derived: false,
                };
              }
            }
          }

          // Multi-line typed-variable: current line starts with .<method>(
          // and one of the prev non-blank lines contains varName (without a method call or decl)
          if (continuationMethod && continuationMethod === methodName) {
            // Check if current trimmed line starts with .<methodName>(
            const contRe = new RegExp(`^\\.${methodEsc}\\s*\\(`);
            if (contRe.test(trimmed)) {
              // Look for varName on previous non-blank lines
              for (const prevLine of prevLines) {
                const prevTrimmed = prevLine.trimStart();
                // prevLine should contain just the varName (possibly with dot-chain start)
                // e.g. "api" or "    api" with no .<method>( after it — the method is on the next line
                // We check: prevLine contains varName as a standalone token
                // and does NOT end with a complete method call chain that we'd already detect
                const varPresent = new RegExp(`\\b${varEsc}\\s*$`).test(prevLine.trimEnd());
                if (varPresent) {
                  // Confirm it's not a declaration line
                  const isDeclPrev = new RegExp(
                    `\\b(?:org\\.openapitools\\.client\\.api\\.)?(?:${Object.keys(JAVA_API_CLASS_TO_ACCESSOR).join("|")})\\s+${varEsc}\\s*=`
                  ).test(prevLine);
                  if (!isDeclPrev) {
                    const pathLen = tvInfo.entry.path ? tvInfo.entry.path.length : 0;
                    const score = pathLen + 2000;
                    if (score > bestScore) {
                      bestScore = score;
                      const methodMatch = /^\.[A-Za-z_][A-Za-z0-9_]*\s*\(/.exec(trimmed);
                      bestMatch = {
                        entry: tvInfo.entry,
                        matchedText: varName + (methodMatch ? methodMatch[0] : "." + methodName + "("),
                        matchIndex: 0,
                        evidence: "sdk_method",
                        derived: false,
                      };
                    }
                    break;
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  return bestMatch;
}

// ---------------------------------------------------------------------------
// redact
// ---------------------------------------------------------------------------

/**
 * Redact credential values from a text string.
 * Handles: key=value, "key": "value", key: value, header/query patterns.
 */
function redact(text) {
  if (!text) return text;

  // 1. Authorization: Bearer <token> — must come first to avoid partial redaction
  text = text.replace(
    /(Authorization\s*:\s*Bearer\s+)([^\s\n'"`,\\]{1,200})/gi,
    "$1[REDACTED]"
  );
  // 2. Authorization: <non-Bearer-token> (header value, whole token)
  text = text.replace(
    /(Authorization\s*:\s*)(?!Bearer\b)([^\s\n'"`,\\]{1,200})/gi,
    "$1[REDACTED]"
  );
  // 3. Bearer <token> standalone (e.g. template: Bearer ${TOKEN})
  text = text.replace(
    /(Bearer\s+)([A-Za-z0-9._\-/+${}]{4,200})/gi,
    "$1[REDACTED]"
  );
  // 4. key = "value" or key = 'value' or key = `value` (quoted)
  text = text.replace(
    /(\b(?:secret|password|passwd|token|api[_-]?key|client[_-]?id|client[_-]?secret)\b\s*[=:]\s*)(['"`][^'"`\n]{0,200}['"`])/gi,
    "$1[REDACTED]"
  );
  // 5. key=value (unquoted, stops at whitespace/comma/quote/etc)
  text = text.replace(
    /(\b(?:secret|password|passwd|token|api[_-]?key|client[_-]?id|client[_-]?secret)\b\s*[=:]\s*)([^\s'"`&,\n\\]{1,100})/gi,
    "$1[REDACTED]"
  );
  // 6. JSON property "key": "value"
  text = text.replace(
    /("(?:secret|password|passwd|token|api[_-]?key|authorization|client[_-]?id|client[_-]?secret|bearer)"\s*:\s*)("(?:[^"\\]|\\.){0,200}")/gi,
    "$1\"[REDACTED]\""
  );

  // 7. Positional credential arguments of SDK client constructors:
  //    new ZuoraClient("id", "secret", env) / new ZuoraClient({ clientId: "..." }) (the object form is covered above).
  text = text.replace(
    /(\bnew\s+\w*Client\s*\()([^)\n]{0,400})(\)?)/g,
    (m, head, args, tail) => head + args.replace(/(['"`])(?:(?!\1)[^\\\n]){1,300}\1/g, "[REDACTED]") + tail
  );
  // 8. Any remaining quoted string that looks like a key (24+ chars of base64/hex/uuid-like text with a digit and a letter)
  text = text.replace(
    /(['"`])(?=[A-Za-z0-9+/=_\-]{24,200}\1)(?=[^'"`]*[0-9])(?=[^'"`]*[A-Za-z])[A-Za-z0-9+/=_\-]{24,200}\1/g,
    "[REDACTED]"
  );

  return text;
}

// ---------------------------------------------------------------------------
// Language detection
// ---------------------------------------------------------------------------

function detectLanguage(filePath) {
  const ext = path.extname(filePath).toLowerCase().replace(/^\./, "");
  return LANGUAGE_MAP[ext] || "other";
}

// ---------------------------------------------------------------------------
// HTTP method detection
// ---------------------------------------------------------------------------

/**
 * Look in the match line and up to 3 previous lines for HTTP method hints.
 * Returns "GET" | "POST" | "PUT" | "PATCH" | "DELETE" | null
 */
function detectHttpMethod(lines, matchLineIdx) {
  // Look at the match line, 3 lines before, and 2 lines after (common pattern: url = ...\nclient.post(url))
  const start = Math.max(0, matchLineIdx - 3);
  const end = Math.min(lines.length - 1, matchLineIdx + 2);
  const context = lines.slice(start, end + 1).join("\n");
  for (const { re, method } of HTTP_METHOD_HINTS) {
    if (re.test(context)) return method;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Confidence determination
// ---------------------------------------------------------------------------

/**
 * @param {string} matchedText
 * @param {Object} entry
 * @param {string} fullLine - the full source line, used to detect /v1/ or /object-query/ context
 */
function determineConfidence(matchedText, entry, fullLine) {
  // High: matched_text starts with /v2 (covers /v2/, /v2?, /v2# and /v2 path-only)
  if (/^\/v2/i.test(matchedText)) {
    return "high";
  }
  // Low: the path is in a URL that looks like a different API version
  // e.g. /v1/accounts or /object-query/accounts
  if (fullLine && /\/v1\/|\/object-query\//i.test(fullLine)) {
    return "low";
  }
  // Medium: URL match without /v2 prefix
  return "medium";
}

// ---------------------------------------------------------------------------
// Comment-line helpers for derived SDK match filtering
// ---------------------------------------------------------------------------

/**
 * Comment-line prefixes per language (trimmed line must start with one of these
 * for the whole line to be skipped for derived detection).
 * Using simple string prefixes — no language parsing needed.
 */
const COMMENT_LINE_PREFIXES = {
  java:       ["//", "*", "/*"],
  javascript: ["//", "*", "/*"],
  python:     ["#"],
  csharp:     ["//", "*", "/*"],
  go:         ["//", "*", "/*"],
  ruby:       ["#"],
  php:        ["//", "#", "*", "/*"],
  shell:      ["#"],
};

/**
 * Return true if the trimmed line is a full-line comment for the given language.
 * Only checks the simple markers; block-comment continuations (lines inside
 * /* ... * /) that begin with whitespace+text are a documented limitation.
 *
 * @param {string} trimmedLine
 * @param {string} language
 * @returns {boolean}
 */
function isCommentLine(trimmedLine, language) {
  const prefixes = COMMENT_LINE_PREFIXES[language];
  if (!prefixes) return false;
  for (const p of prefixes) {
    if (trimmedLine.startsWith(p)) return true;
  }
  return false;
}

/**
 * Strip a trailing line comment from the line, respecting quoted strings so
 * that `//` inside `"https://..."` is not treated as a comment start.
 * Only handles single-line comment markers for the given language.
 *
 * @param {string} line
 * @param {string} language
 * @returns {string} line with trailing comment removed
 */
function stripTrailingComment(line, language) {
  // Only // comments need stripping (# for python/ruby/shell/php, but those
  // languages do not embed // inside URLs in the same way; still handle both).
  const slashLangs = new Set(["java", "javascript", "csharp", "go", "php"]);
  const hashLangs  = new Set(["python", "ruby", "shell", "php"]);

  const useSlash = slashLangs.has(language);
  const useHash  = hashLangs.has(language);

  if (!useSlash && !useHash) return line;

  // Walk the line character by character, tracking quoted string state.
  let inSingle = false;
  let inDouble = false;
  let inBacktick = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];

    // Toggle string delimiters (no escape handling needed for our purpose —
    // we just need to avoid stripping // or # inside a string literal)
    if (ch === "'" && !inDouble && !inBacktick) { inSingle = !inSingle; continue; }
    if (ch === '"' && !inSingle && !inBacktick) { inDouble = !inDouble; continue; }
    if (ch === '`' && !inSingle && !inDouble)   { inBacktick = !inBacktick; continue; }

    if (inSingle || inDouble || inBacktick) continue;

    // Check for // comment
    if (useSlash && ch === "/" && i + 1 < line.length && line[i + 1] === "/") {
      return line.slice(0, i).trimEnd();
    }
    // Check for # comment (only outside strings)
    if (useHash && ch === "#") {
      return line.slice(0, i).trimEnd();
    }
  }
  return line;
}

/**
 * Return true if the line looks like a method/function definition that contains
 * the derived name as the defined method (not a call site).
 *
 * Patterns detected (language-aware):
 *   - def <name>(    — Ruby, Python
 *   - func <name>(   — Go
 *   - function <name>(   — PHP, JavaScript
 *   - fn <name>(     — Rust (not in our set, future-proof)
 *   - sub <name>(    — Perl (not in our set)
 *   - <type/modifier tokens> <name>( line ends with { or :
 *     where modifier tokens are: public, private, protected, static, async,
 *     override, virtual, abstract, void, Task, Task<...>, async Task, etc.
 *
 * @param {string} line      - original source line (not trimmed)
 * @param {string} name      - derived method name (no parens)
 * @param {string} language
 * @returns {boolean}
 */
function isDefinitionLine(line, name, language) {
  const trimmed = line.trimStart();

  // Ruby / Python: def <name>(
  if (language === "ruby" || language === "python") {
    // "def name(" or "def name (" possibly with spaces
    if (/^\s*(?:async\s+)?def\s+/.test(line)) {
      const defRe = new RegExp(`\\bdef\\s+${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\(`);
      if (defRe.test(line)) return true;
    }
    return false;
  }

  // Go: func <something> <name>(  or  func <name>(
  if (language === "go") {
    if (/^\s*func\s+/.test(line)) {
      // "func Name(" or "func (recv *T) Name(": an optional parenthesized receiver before the name
      const funcRe = new RegExp(`\\bfunc\\s+(?:\\([^)]*\\)\\s*)?${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\(`);
      if (funcRe.test(line)) return true;
    }
    return false;
  }

  // PHP / JavaScript: function <name>(
  if (language === "php" || language === "javascript") {
    if (/\bfunction\s+/.test(trimmed)) {
      const fnRe = new RegExp(`\\bfunction\\s+${name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\s*\\(`);
      if (fnRe.test(line)) return true;
    }
  }

  // Java / C# / JavaScript / PHP: typed method declaration.
  // Heuristic: the matched name is immediately preceded (after spaces) by a word-char token
  // that looks like a type or modifier AND the line ends with '{' or ':'.
  // Type/modifier tokens: word characters (type names, void, Task, async, public, etc.)
  // plus optional generic suffix like <...> or [].
  // We require the line (trimmed) ends with '{' or ':' to reduce false positives.
  const lineEnd = trimmed.trimEnd();
  if (lineEnd.endsWith("{") || lineEnd.endsWith(":")) {
    // Check that <name>( is preceded by a type-like token
    const nameEsc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    // Token before name: a word boundary + word chars + optional <>[] + whitespace
    const typedDefRe = new RegExp(
      `\\b[A-Za-z_][A-Za-z0-9_]*(?:<[^>]*>|\\[\\])*\\s+${nameEsc}\\s*\\(`
    );
    if (typedDefRe.test(line)) return true;
  }

  return false;
}

// ---------------------------------------------------------------------------
// Match a single line against all patterns, return best match
// ---------------------------------------------------------------------------

/**
 * Try to match a text line against all compiled entries.
 * Returns the best match (most specific / longest path) or null.
 *
 * Priority:
 *   1. Java exact sdk_method (accessor-chain or typed-var) — score = pathLen + 2000
 *   2. Explicit sdk_method (non-Java, high confidence) — score = pathLen + 2000
 *   3. Derived sdk_method (medium confidence) — score = pathLen + 1000
 *      Only emitted when hasSdkContext === true AND derive_from_operation_id is true
 *   4. URL regex — score = pathLen
 *
 * Disambiguation: within the same priority tier, longest operationId/path wins.
 * An explicit sdk_method on the same line always beats a derived one.
 *
 * For derived matches only: lines that are full-line comments, or contain only
 * a method/function definition (not a call), are skipped.
 *
 * @param {string} line
 * @param {Object[]} compiledEntries
 * @param {string} language
 * @param {string} pathPrefix
 * @param {boolean} hasSdkContext - true if the file contains a Zuora SDK import/reference
 * @param {Object|null} javaMatch - pre-computed Java match (from matchJavaLine) or null
 */
function matchLine(line, compiledEntries, language, pathPrefix, hasSdkContext, javaMatch) {
  if (line.length > MAX_LINE_LENGTH) return null;

  let bestMatch = null;
  let bestScore = -1;

  // Apply pre-computed Java match first (if provided)
  if (javaMatch) {
    const pathLen = javaMatch.entry.path ? javaMatch.entry.path.length : 0;
    const score = pathLen + 2000;
    if (score > bestScore) {
      bestScore = score;
      bestMatch = javaMatch;
    }
  }

  // Pre-compute comment and definition state for derived-only checks.
  // URL-regex and explicit SDK matches are not affected by these guards.
  let derivedLineAllowed = null; // lazily computed
  let strippedLine = null;       // lazily computed (comment-stripped version)

  function getDerivedLineAllowed() {
    if (derivedLineAllowed !== null) return derivedLineAllowed;
    const trimmed = line.trimStart();
    // (a) Skip full-line comments
    if (isCommentLine(trimmed, language)) {
      derivedLineAllowed = false;
      return false;
    }
    derivedLineAllowed = true;
    return true;
  }

  function getStrippedLine() {
    if (strippedLine !== null) return strippedLine;
    strippedLine = stripTrailingComment(line, language);
    return strippedLine;
  }

  for (const entry of compiledEntries) {
    const pathLen = entry.path ? entry.path.length : 0;

    // URL regex match (not affected by comment guards)
    if (entry.compiledRe) {
      // Reset lastIndex for stateful regexes (if 'g' flag)
      entry.compiledRe.lastIndex = 0;
      const m = entry.compiledRe.exec(line);
      if (m) {
        const score = pathLen;
        if (score > bestScore) {
          bestScore = score;
          bestMatch = {
            entry,
            matchedText: m[0],
            matchIndex: m.index,
            evidence: "url_regex",
            derived: false,
          };
        }
      }
    }

    // Explicit SDK method match for non-Java languages (score = pathLen + 2000, not affected by comment guards)
    if (language && language !== "java" && entry.sdkPatterns && entry.sdkPatterns[language]) {
      const sdkRe = entry.sdkPatterns[language];
      sdkRe.lastIndex = 0;
      const m = sdkRe.exec(line);
      if (m) {
        const score = pathLen + 2000;
        if (score > bestScore) {
          bestScore = score;
          bestMatch = {
            entry,
            matchedText: m[0],
            matchIndex: m.index,
            evidence: "sdk_method",
            derived: false,
          };
        }
      }
    }

    // Derived SDK method match (score = pathLen + 1000)
    // Only when the file has Zuora SDK context and language is supported.
    // Skipped for full-line comments and method definition lines.
    if (hasSdkContext && language && entry.derivedSdkPatterns && entry.derivedSdkPatterns[language]) {
      // (a) Skip full-line comments
      if (!getDerivedLineAllowed()) continue;

      const derivedRe = entry.derivedSdkPatterns[language];
      derivedRe.lastIndex = 0;
      // (b) Strip trailing comment before matching (preserves string literal //)
      const lineToMatch = getStrippedLine();
      const m = derivedRe.exec(lineToMatch);
      if (m) {
        // (c) Skip definition lines: check each matched name against the line
        const matchedName = m[1]; // capture group 1 is the method name
        if (matchedName && isDefinitionLine(line, matchedName, language)) {
          continue;
        }
        const score = pathLen + 1000;
        if (score > bestScore) {
          bestScore = score;
          bestMatch = {
            entry,
            matchedText: m[0],
            matchIndex: m.index,
            evidence: "sdk_method",
            derived: true,
          };
        }
      }
    }
  }

  return bestMatch;
}

// ---------------------------------------------------------------------------
// Unmatched v2 URL detection
// ---------------------------------------------------------------------------

/**
 * Check if a line has a v2-prefixed URL that wasn't matched by any entry.
 * Only fragments that start with /v2/ (leading slash required) are reported.
 */
function findUnmatchedV2(line, compiledEntries, pathPrefix) {
  if (line.length > MAX_LINE_LENGTH) return null;
  // Look for /v2/ patterns — require leading slash so bare "v2/accounts/" is not reported
  const v2Re = /\/v2\/[a-zA-Z0-9_\-\/{}$%]+/g;
  let m;
  while ((m = v2Re.exec(line)) !== null) {
    const candidate = m[0];
    // Double-check candidate starts with /v2/ (the regex guarantees this, but be explicit)
    if (!candidate.startsWith("/v2/")) continue;
    // Check if it's matched by any entry
    let matched = false;
    for (const entry of compiledEntries) {
      if (entry.compiledRe) {
        entry.compiledRe.lastIndex = 0;
        if (entry.compiledRe.test(candidate) || entry.compiledRe.test(line)) {
          matched = true;
          break;
        }
      }
    }
    if (!matched) {
      return candidate;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Risk detection helpers
// ---------------------------------------------------------------------------

/**
 * Classify what kind of ZuoraClient import is present in the file text.
 * Returns:
 *   "sdk_only"    — imports com.zuora.sdk.ZuoraClient but NOT com.zuora.ZuoraClient
 *   "v1_only"     — imports com.zuora.ZuoraClient but NOT com.zuora.sdk.ZuoraClient
 *   "both"        — imports both
 *   "neither"     — imports neither (but may have other v2 context like quickStartApi)
 */
function classifyJavaZuoraClientImport(fileText) {
  const hasSdkImport = /\bimport\s+com\.zuora\.sdk\.ZuoraClient\s*;/.test(fileText);
  const hasV1Import  = /\bimport\s+com\.zuora\.ZuoraClient\s*;/.test(fileText);
  if (hasSdkImport && hasV1Import) return "both";
  if (hasSdkImport) return "sdk_only";
  if (hasV1Import)  return "v1_only";
  return "neither";
}

function detectRisks(line, language, filePath, hasJavaV2Context, javaClientImportKind) {
  const risks = [];
  if (line.length > MAX_LINE_LENGTH) return risks;

  // Skip comment lines for risk detection (avoids false positives from doc comments)
  const trimmed = line.trimStart();
  if (isCommentLine(trimmed, language)) return risks;

  // base_url_variable: v2 path appended to a variable, no host in the line
  if (BASE_URL_VAR_RE.test(line) && !/https?:\/\//i.test(line)) {
    risks.push({
      kind: "base_url_variable",
      note: `Line appears to append a v2 path to a variable: ${redact(line).slice(0, 120)}`,
    });
  }

  // dynamic_url: /v2 prefix built by concatenation
  if (DYNAMIC_URL_RE.test(line)) {
    risks.push({
      kind: "dynamic_url",
      note: `v2 prefix appears to be built by string concatenation: ${redact(line).slice(0, 120)}`,
    });
  }

  // Java v2 SDK client construction (only in Java files with v2 context)
  if (language === "java") {
    // quickStartApi: unified client path
    if (JAVA_QUICKSTART_RE.test(line)) {
      risks.push({
        kind: "v2_sdk_client_construction",
        note: `unified client with quickStartApi(): ${redact(line).slice(0, 120)}`,
      });
    } else if (JAVA_V2_DIRECT_CLIENT_RE.test(line)) {
      // Direct v2 client: new ZuoraClient( or new com.zuora.sdk.ZuoraClient(
      // Classification:
      //   - new com.zuora.sdk.ZuoraClient( — always the v2 direct client
      //   - new com.zuora.ZuoraClient(     — always the v1 unified client (never report as v2)
      //   - new ZuoraClient( (unqualified):
      //     * import "sdk_only"  → is the v2 SDK client → report
      //     * import "v1_only"   → is the v1 unified client → do NOT report
      //     * import "both"      → ambiguous; only fully-qualified constructions are classified
      //                            so unqualified form is skipped
      //     * import "neither"   → no direct ZuoraClient import; may have quickStartApi context;
      //                            fall back to generic v2 context heuristic (report only if
      //                            hasJavaV2Context with no v1-only import)
      const isFqnV2 = /\bnew\s+com\.zuora\.sdk\.ZuoraClient\s*\(/.test(line);
      const isV1Fqn = /\bnew\s+com\.zuora\.ZuoraClient\s*\(/.test(line);

      if (isV1Fqn) {
        // Explicit fully-qualified v1 client — never a v2 direct-client risk
      } else if (isFqnV2) {
        // Explicit fully-qualified v2 SDK client — always report
        risks.push({
          kind: "v2_sdk_client_construction",
          note: `direct v2 client (com.zuora.sdk.ZuoraClient): ${redact(line).slice(0, 120)}`,
        });
      } else {
        // Unqualified new ZuoraClient( — classify by imports
        const kind = javaClientImportKind || "neither";
        let shouldReport = false;
        if (kind === "sdk_only") {
          // Only v2 SDK imported — this is clearly the v2 client
          shouldReport = true;
        } else if (kind === "v1_only") {
          // Only v1 unified client imported — this is the v1 client, not v2
          shouldReport = false;
        } else if (kind === "both") {
          // Both imported — unqualified form is ambiguous; skip (only FQN is classified above)
          shouldReport = false;
        } else {
          // Neither import present but has v2 context (e.g. quickStartApi, FQN usage)
          // Fall back to the hasJavaV2Context flag (without isV1Fqn check already done above)
          shouldReport = hasJavaV2Context;
        }
        if (shouldReport) {
          risks.push({
            kind: "v2_sdk_client_construction",
            note: `direct v2 client (com.zuora.sdk.ZuoraClient): ${redact(line).slice(0, 120)}`,
          });
        }
      }
    }
  }

  // JavaScript wrapper_idiom (kept for backward compat)
  if (language === "javascript" && WRAPPER_IDIOM_JS.test(line)) {
    risks.push({
      kind: "v2_sdk_client_construction",
      note: `ZuoraClient construction detected (JavaScript): ${redact(line).slice(0, 120)}`,
    });
  }

  return risks;
}

// ---------------------------------------------------------------------------
// ipaas_or_collection_file detection
// ---------------------------------------------------------------------------

function isIpaasOrCollectionFile(filePath, content) {
  const basename = path.basename(filePath).toLowerCase();
  if (basename.includes(".postman_collection")) return true;
  // JSON/XML/YAML files that contain a v2 URL
  const ext = path.extname(filePath).toLowerCase();
  if ([".json", ".xml", ".yaml", ".yml"].includes(ext)) {
    if (/\/v2\//i.test(content)) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// Binary file detection
// ---------------------------------------------------------------------------

function isBinaryFile(buf) {
  const check = Math.min(buf.length, BINARY_CHECK_BYTES);
  for (let i = 0; i < check; i++) {
    if (buf[i] === 0) return true;
  }
  return false;
}

// ---------------------------------------------------------------------------
// scanText — scan a string of source code
// ---------------------------------------------------------------------------

/**
 * Scan a text string for v2 usage.
 *
 * @param {string} text - file contents
 * @param {string} relPath - path relative to root (for output)
 * @param {Object} patterns - compiled patterns from loadPatterns
 * @param {number} contextLines - lines of context to include in snippets
 * @returns {{ sites, unmatched, risks, longLinesSkipped }}
 */
function scanText(text, relPath, patterns, contextLines) {
  contextLines = contextLines !== undefined ? contextLines : DEFAULT_CONTEXT_LINES;
  const language = detectLanguage(relPath);
  const lines = text.split("\n");
  const sites = [];
  const unmatched = [];
  const risks = [];
  let longLinesSkipped = 0;

  // ipaas check
  const isIpaas = isIpaasOrCollectionFile(relPath, text);

  // Determine SDK context for the whole file.
  // Derived SDK method detection only fires if the file shows Zuora SDK context.
  const hasSdkContext = SDK_CONTEXT_PATTERNS.some((re) => re.test(text));

  // For Java files: determine v2 SDK context and extract typed variable declarations.
  const javaV2Context = language === "java" ? hasJavaV2SdkContext(text) : false;
  const javaVarToAccessor = language === "java" && javaV2Context
    ? extractJavaTypedVars(text, patterns.javaTypedVarInfo || [])
    : {};
  // For Java: classify the ZuoraClient import for accurate construction risk detection
  const javaClientImportKind = language === "java" ? classifyJavaZuoraClientImport(text) : null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.length > MAX_LINE_LENGTH) {
      longLinesSkipped++;
      continue;
    }

    // Risk detection (non-capturing)
    const lineRisks = detectRisks(line, language, relPath, javaV2Context, javaClientImportKind);
    for (const risk of lineRisks) {
      risks.push({
        file: relPath,
        line: i + 1,
        kind: risk.kind,
        note: risk.note,
      });
    }

    // Java exact SDK match (only for Java files with v2 context)
    let javaMatch = null;
    if (language === "java" && javaV2Context) {
      // Collect previous non-blank non-comment lines (up to 3) for multi-line chain detection
      const prevLines = prevNonBlankLines(lines, i, 3);
      javaMatch = matchJavaLine(
        line,
        patterns.javaAccessorChains || [],
        javaVarToAccessor,
        patterns.javaTypedVarInfo || [],
        javaV2Context,
        prevLines
      );
    }

    // URL/SDK match — pass hasSdkContext so derived patterns are only tried
    // in files with a Zuora SDK import/reference.
    const match = matchLine(line, patterns.compiledEntries, language, patterns.pathPrefix, hasSdkContext, javaMatch);
    if (match) {
      const rawMatchedText = match.matchedText;
      const matchedText = redact(rawMatchedText);
      const contextStart = Math.max(0, i - contextLines);
      const contextEnd = Math.min(lines.length - 1, i + contextLines);
      let snippet = lines.slice(contextStart, contextEnd + 1).join("\n");
      snippet = redact(snippet);
      // Cap snippet
      if (snippet.length > 600) snippet = snippet.slice(0, 597) + "...";
      // Also cap to 12 lines
      const snippetLines = snippet.split("\n");
      if (snippetLines.length > 12) {
        snippet = snippetLines.slice(0, 12).join("\n");
      }

      // Confidence:
      //   - Explicit sdk_method (Java exact or non-Java explicit) → "high"
      //   - Derived sdk_method  → "medium"
      //   - URL regex           → determined by path prefix
      let confidence;
      if (match.evidence === "sdk_method") {
        confidence = match.derived ? "medium" : "high";
      } else {
        confidence = determineConfidence(rawMatchedText, match.entry, line);
      }

      // http_method: for SDK matches, use the entry's method (always GET for v2)
      const httpMethod = (match.evidence === "sdk_method")
        ? (match.entry.method || "GET")
        : detectHttpMethod(lines, i);

      const notes = [];
      if (match.derived) {
        notes.push("sdk_method_derived_from_operation_id");
      } else if (httpMethod && httpMethod !== "GET" && httpMethod !== null) {
        // Note if non-GET on a read-only pack (only for non-derived matches)
        const packMethod = match.entry.method || "GET";
        if (packMethod === "GET") {
          notes.push(`non_get_method: this operation is read-only in the pack`);
        }
      }

      // Column: 1-based index of the match in the line
      const column = match.matchIndex + 1;

      sites.push({
        file: relPath,
        line: i + 1,
        column,
        language,
        pack_id: match.entry.card_id,
        evidence: match.evidence,
        confidence,
        http_method: httpMethod,
        matched_text: matchedText,
        snippet,
        notes: notes.length > 0 ? notes : undefined,
      });
    } else {
      // Check for unmatched v2 URL
      const unm = findUnmatchedV2(line, patterns.compiledEntries, patterns.pathPrefix);
      if (unm) {
        const contextStart = Math.max(0, i - contextLines);
        const contextEnd = Math.min(lines.length - 1, i + contextLines);
        let snippet = lines.slice(contextStart, contextEnd + 1).join("\n");
        snippet = redact(snippet);
        if (snippet.length > 600) snippet = snippet.slice(0, 597) + "...";
        unmatched.push({
          file: relPath,
          line: i + 1,
          language,
          matched_text: redact(unm),
          snippet,
        });
      }
    }
  }

  // ipaas_or_collection_file risk for this file
  if (isIpaas) {
    risks.push({
      file: relPath,
      line: 0,
      kind: "ipaas_or_collection_file",
      note: `File appears to be a Postman collection or iPaaS export containing v2 URLs`,
    });
  }

  return { sites, unmatched, risks, longLinesSkipped };
}

// ---------------------------------------------------------------------------
// scanDirectory — walk a directory tree
// ---------------------------------------------------------------------------

/**
 * Walk a directory tree and scan all eligible files.
 *
 * @param {string} rootPath - absolute path to codebase root
 * @param {Object} patterns - compiled patterns from loadPatterns
 * @param {number} contextLines - lines of context
 * @returns inventory object
 */
function scanDirectory(rootPath, patterns, contextLines) {
  contextLines = contextLines !== undefined ? contextLines : DEFAULT_CONTEXT_LINES;

  const allSites = [];
  const allUnmatched = [];
  const allRisks = [];
  let filesScanned = 0;
  let filesSkipped = 0;
  let longLinesSkipped = 0;
  let truncated = false;
  // visitedRealPaths tracks both directories (to prevent re-walking) and files
  // (to prevent scanning the same inode twice via different symlinked paths).
  // The root directory is seeded here so a symlink inside the root that points
  // back to the root itself is recognised as already visited on the first pass.
  const visitedRealPaths = new Set();

  // Resolve root real path to detect symlink escapes
  let rootRealPath;
  try {
    rootRealPath = fs.realpathSync(rootPath);
  } catch (_) {
    rootRealPath = rootPath;
  }
  // Seed with the root so loop-symlinks back to root are caught immediately
  visitedRealPaths.add(rootRealPath);

  function walk(dir) {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (_) {
      return;
    }

    // Sort for determinism
    entries.sort((a, b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0);

    for (const entry of entries) {
      if (filesScanned >= MAX_FILES) {
        truncated = true;
        return;
      }

      const fullPath = path.join(dir, entry.name);

      if (entry.isSymbolicLink()) {
        let realTarget;
        try {
          realTarget = fs.realpathSync(fullPath);
        } catch (_) {
          continue;
        }
        // Do not follow symlinks that leave the root
        if (!realTarget.startsWith(rootRealPath + path.sep) && realTarget !== rootRealPath) {
          continue;
        }
        // Recurse if directory symlink, or scan if file symlink (treat as file)
        let stat;
        try { stat = fs.statSync(fullPath); } catch (_) { continue; }
        if (stat.isDirectory()) {
          // Avoid directory loops — add the real target before descending so that
          // any symlink inside pointing back to this same directory is skipped.
          if (visitedRealPaths.has(realTarget)) continue;
          visitedRealPaths.add(realTarget);
          walk(fullPath);
        } else {
          // For file symlinks, do NOT add to visitedRealPaths here.
          // processFile is the single decision point for file deduplication:
          // it resolves the real path, checks-then-adds, so the first path in
          // sorted order wins and subsequent paths (real or symlinked) to the
          // same inode are skipped there.
          processFile(fullPath, dir);
        }
        continue;
      }

      if (entry.isDirectory()) {
        // Skip blacklisted dirs (also skip .git-named dirs)
        const name = entry.name;
        if (SKIP_DIRS.has(name)) continue;
        // Also skip dirs starting with .git (e.g. .git-backup)
        if (name.startsWith(".git")) continue;
        // Deduplicate real paths for regular directories to prevent loops via
        // bind-mounts or hard-linked directories (mirrors the symlink guard)
        let realDirPath;
        try { realDirPath = fs.realpathSync(fullPath); } catch (_) { realDirPath = fullPath; }
        if (visitedRealPaths.has(realDirPath)) continue;
        visitedRealPaths.add(realDirPath);
        walk(fullPath);
      } else if (entry.isFile()) {
        processFile(fullPath, dir);
      }
    }
  }

  function processFile(fullPath, dir) {
    if (allSites.length >= MAX_SITES) {
      truncated = true;
      return;
    }

    // Deduplicate files by real path so a symlinked file that points to a
    // regular file already scanned is not reported a second time.
    let realFilePath;
    try { realFilePath = fs.realpathSync(fullPath); } catch (_) { realFilePath = fullPath; }
    if (visitedRealPaths.has(realFilePath)) return;
    visitedRealPaths.add(realFilePath);

    let stat;
    try { stat = fs.statSync(fullPath); } catch (_) { filesSkipped++; return; }
    if (stat.size > MAX_FILE_SIZE) { filesSkipped++; return; }

    let buf;
    try { buf = fs.readFileSync(fullPath); } catch (_) { filesSkipped++; return; }

    if (isBinaryFile(buf)) { filesSkipped++; return; }

    let text;
    try { text = buf.toString("utf8"); } catch (_) { filesSkipped++; return; }

    const relPath = path.relative(rootPath, fullPath).split(path.sep).join("/");
    filesScanned++;

    const result = scanText(text, relPath, patterns, contextLines);
    allSites.push(...result.sites);
    allUnmatched.push(...result.unmatched);
    allRisks.push(...result.risks);
    longLinesSkipped += result.longLinesSkipped;
  }

  walk(rootPath);

  // Sort sites deterministically: file, line, column
  allSites.sort((a, b) => {
    if (a.file < b.file) return -1;
    if (a.file > b.file) return 1;
    if (a.line !== b.line) return a.line - b.line;
    return a.column - b.column;
  });

  // Hard cap after sort
  if (allSites.length > MAX_SITES) {
    truncated = true;
    allSites.length = MAX_SITES;
  }

  // Assign stable IDs
  const sites = allSites.map((s, i) => {
    const id = `S${String(i + 1).padStart(3, "0")}`;
    const site = { id, ...s };
    if (!site.notes) delete site.notes;
    return site;
  });

  // Build summary
  const byPackId = {};
  for (const s of sites) {
    if (s.pack_id) {
      byPackId[s.pack_id] = (byPackId[s.pack_id] || 0) + 1;
    }
  }

  const summary = {
    files_scanned: filesScanned,
    files_skipped: filesSkipped,
    sites: sites.length,
    by_pack_id: byPackId,
    unmatched_v2_urls: allUnmatched.length,
    undetected_risk: allRisks.length,
    long_lines_skipped: longLinesSkipped,
  };

  if (truncated) {
    summary.truncated = true;
    summary.truncation_note = `Scan capped at ${MAX_FILES} files / ${MAX_SITES} sites`;
  }

  // languages_without_sdk_pattern: from patterns file
  // For B73: non-java scanner languages are URL-only
  summary.languages_without_sdk_pattern = patterns.langsWithoutSdkPattern
    ? [...patterns.langsWithoutSdkPattern].sort()
    : [];

  // Add sdk_detection summary
  if (patterns.sdkDetection) {
    summary.sdk_detection = patterns.sdkDetection;
  }

  return { summary, sites, unmatched: allUnmatched, undetected_risk: allRisks };
}

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

function main(argv) {
  const args = argv.slice(2);

  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    process.stderr.write(
      "Usage: node scan-v2-usage.js <codebase-path> [--patterns <file>] [--out <file>] [--context-lines N]\n" +
      "Exit codes: 0 = success (even with zero sites), 2 = usage error or unreadable path\n\n" +
      "Output fields:\n" +
      "  summary.languages_without_sdk_pattern — always present as an array; lists scanner\n" +
      "    languages for which no v2 SDK is available (URL detection only). For B73 this is\n" +
      "    all languages except java.\n" +
      "  summary.sdk_detection — { explicit: [...], derived: [...] } listing which languages\n" +
      "    have exact SDK method detection (explicit) or derived name detection (derived).\n" +
      "    To re-enable derived detection for future SDKs, set derive_from_operation_id: true\n" +
      "    in the patterns file.\n\n" +
      "Java SDK detection (B73):\n" +
      "  - Accessor-chain: .<accessor>().<method>( e.g. client.accounts().getAccounts(\n" +
      "  - Typed-variable: AccountsApi api = client.accounts(); api.getAccounts(\n" +
      "  - Requires v2 context: com.zuora.sdk import, org.openapitools.client import, or quickStartApi(\n" +
      "  - billingDocuments().get( is NOT one of the nine operations\n" +
      "  - accountsApi() etc (v1 unified client) are never reported\n\n" +
      "Known limitations:\n" +
      "  - Multi-line URL construction may be missed (scanner reads one line at a time).\n" +
      "  - Multi-line Java accessor chains are supported up to 3 intervening blank/comment lines.\n" +
      "  - Dynamic/concatenated URLs produce base_url_variable or dynamic_url risk notes but the\n" +
      "    endpoint cannot be confirmed.\n" +
      "  - Full-line comments are skipped for derived SDK detection; block-comment continuations\n" +
      "    (lines inside /* ... */ that do not start with //) are not recognized as comments.\n" +
      "  - SDK version is not verified; method names are matched structurally.\n" +
      "  - Wrapper classes that rename v2 SDK methods are not detected.\n" +
      "  - SDK calls through reflection are not detected.\n" +
      "  - A derived SDK match takes the whole line (one site per line); a derived match on a\n" +
      "    line suppresses any URL regex match for a different operation on that same line.\n" +
      "  - JAVA_ACCESSOR_TO_API_CLASS and detection-patterns.json must both be updated when a\n" +
      "    new v2 API class (pack) is added to the Java SDK.\n"
    );
    process.exit(2);
  }

  // Parse args
  let codebasePath = null;
  let patternsFile = null;
  let outFile = null;
  let contextLines = DEFAULT_CONTEXT_LINES;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--patterns" && args[i + 1]) {
      patternsFile = args[++i];
    } else if (args[i] === "--out" && args[i + 1]) {
      outFile = args[++i];
    } else if (args[i] === "--context-lines" && args[i + 1]) {
      contextLines = parseInt(args[++i], 10);
      if (isNaN(contextLines) || contextLines < 0) contextLines = DEFAULT_CONTEXT_LINES;
    } else if (!args[i].startsWith("--")) {
      codebasePath = args[i];
    }
  }

  if (!codebasePath) {
    process.stderr.write("Error: codebase-path is required\n");
    process.exit(2);
  }

  // Resolve codebase path
  const absCodebasePath = path.resolve(codebasePath);
  try {
    const stat = fs.statSync(absCodebasePath);
    if (!stat.isDirectory()) {
      process.stderr.write(`Error: ${codebasePath} is not a directory\n`);
      process.exit(2);
    }
  } catch (e) {
    process.stderr.write(`Error: cannot read ${codebasePath}: ${e.message}\n`);
    process.exit(2);
  }

  // Resolve patterns file
  if (!patternsFile) {
    patternsFile = path.join(__dirname, "..", "references", "v2-v1", "detection-patterns.json");
  }
  patternsFile = path.resolve(patternsFile);

  let patterns;
  try {
    patterns = loadPatterns(patternsFile);
  } catch (e) {
    process.stderr.write(`Error: cannot load patterns from ${patternsFile}: ${e.message}\n`);
    process.exit(2);
  }

  process.stderr.write(`Scanning ${absCodebasePath}...\n`);

  const result = scanDirectory(absCodebasePath, patterns, contextLines);

  // Compute relative patterns file for output
  const relPatternsFile = path.relative(absCodebasePath, patternsFile).split(path.sep).join("/") ||
    patternsFile;

  const inventory = {
    scanner_version: SCANNER_VERSION,
    patterns_file: relPatternsFile,
    root: codebasePath,
    summary: result.summary,
    sites: result.sites,
    unmatched: result.unmatched,
    undetected_risk: result.undetected_risk,
  };

  const json = JSON.stringify(inventory, null, 2) + "\n";

  if (outFile) {
    fs.writeFileSync(path.resolve(outFile), json, "utf8");
    process.stderr.write(`Inventory written to ${outFile}\n`);
  } else {
    process.stdout.write(json);
  }

  process.stderr.write(
    `Done: ${result.summary.files_scanned} files scanned, ` +
    `${result.summary.files_skipped} skipped, ` +
    `${result.summary.sites} sites found.\n`
  );

  // Do not call process.exit() on the success path when writing to stdout.
  // Calling process.exit() before the pipe is drained truncates large outputs.
  // Setting process.exitCode lets the process exit naturally after all I/O flushes.
  process.exitCode = 0;
}

if (require.main === module) main(process.argv);

module.exports = { scanDirectory, scanText, redact, loadPatterns, deriveSdkNames };
