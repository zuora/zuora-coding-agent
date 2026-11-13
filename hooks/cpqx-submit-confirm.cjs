#!/usr/bin/env node
// PreToolUse hook: submit_cpqx_quote sends a quote to Zuora billing and cannot be undone, so Claude Code asks the
// user directly (even when the tool is otherwise auto-approved) instead of letting the model decide.
let input = '';
process.stdin.on('data', (chunk) => { input += chunk; });
process.stdin.on('end', () => {
  let event;
  try {
    event = JSON.parse(input);
  } catch {
    process.exit(0);
  }
  const tool = String(event.tool_name || '');
  const args = event.tool_input || {};
  if (!tool.endsWith('__manage_cpqx_quotes') || args.operation !== 'submit_cpqx_quote') {
    process.exit(0);
  }
  const quote = typeof args.quoteId === 'string' ? args.quoteId : 'this quote';
  process.stdout.write(JSON.stringify({
    hookSpecificOutput: {
      hookEventName: 'PreToolUse',
      permissionDecision: 'ask',
      permissionDecisionReason: `Send quote ${quote} to Zuora billing? This creates an order and a subscription `
        + 'in Zuora and cannot be undone.',
    },
  }));
  process.exit(0);
});
