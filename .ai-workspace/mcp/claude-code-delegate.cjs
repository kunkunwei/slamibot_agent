#!/usr/bin/env node
'use strict';

const readline = require('node:readline');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const SERVER_NAME = 'slamibot-claude-code-delegate';
const SERVER_VERSION = '1.1.0';
const DEFAULT_TIMEOUT_MS = 600_000;
const DEFAULT_BUDGET_USD = 2;
const MAX_CONCURRENCY = Math.min(Math.max(Number(process.env.CLAUDE_CODE_MAX_CONCURRENCY || 2), 1), 4);
const pendingJobs = [];
let activeJobs = 0;

function send(message) {
  process.stdout.write(`${JSON.stringify(message)}\n`);
}

function textResult(text, isError = false) {
  return { content: [{ type: 'text', text }], isError };
}

function splitAllowedRoots(value) {
  return (value || '')
    .split(path.delimiter)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => path.resolve(item));
}

function isWithin(candidate, root) {
  const relative = path.relative(root, candidate);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

function resolveWorkingDirectory(requested) {
  const candidate = path.resolve(requested || process.cwd());
  if (!fs.existsSync(candidate) || !fs.statSync(candidate).isDirectory()) {
    throw new Error(`cwd is not an existing directory: ${candidate}`);
  }

  const roots = splitAllowedRoots(process.env.CLAUDE_CODE_MCP_ALLOWED_ROOTS);
  if (roots.length > 0 && !roots.some((root) => isWithin(candidate, root))) {
    throw new Error(`cwd is outside CLAUDE_CODE_MCP_ALLOWED_ROOTS: ${candidate}`);
  }
  return candidate;
}

function buildPrompt(prompt, mode, cwd, lane) {
  let constraints;
  if (mode === 'edit') {
    constraints = [
      'You are a Claude Code sub-agent delegated by Codex.',
      `Team lane: ${lane}`,
      `Authorized working directory: ${cwd}`,
      'Follow all repository instructions, including AGENTS.md and CLAUDE.md when present.',
      'Modify only files explicitly required by the delegated task.',
      'Do not run shell commands, alter Git history, push, publish, connect to remote machines, or expand scope.',
      'Use the fast path: one bounded implementation pass, no backup, no tests, no build, and no self-directed fix/test loop unless the delegated task explicitly requests it.',
      'At the end return a concise handoff: lane, status, changed files, change summary, tests: SKIPPED (user fast mode), and what the user should manually observe during integration.',
    ];
  } else if (mode === 'jetson_read_only') {
    const helper = (process.env.JETSON_READONLY_HELPER || 'F:/slamibot_agent/.ai-workspace/mcp/jetson-readonly.cjs').replace(/\\/g, '/');
    constraints = [
      'You are a read-only Claude Code sub-agent delegated by Codex with controlled Jetson SSH inspection access.',
      `Team lane: ${lane}`,
      `Authorized local working directory: ${cwd}`,
      'Follow all repository instructions, including AGENTS.md and CLAUDE.md when present.',
      'Local files are read-only. Do not edit files, alter Git, publish, push, or connect to any host directly.',
      `The only permitted remote command entry is: node ${helper} <operation> [argument]`,
      'Allowed operations are: identity, uptime, disk, ports, docker-ps, docker-logs <allowlisted-container> [tail], git-status <ros1|ros2|external_3d>, ros1-nodes, ros2-nodes.',
      'Never invoke ssh directly. Never run build, deploy, restart, stop, start, rm, prune, reboot, package installation, or arbitrary remote commands.',
      'Return the commands used, relevant output summary, facts versus assumptions, and recommended next steps.',
    ];
  } else {
    constraints = [
      'You are a read-only Claude Code sub-agent delegated by Codex.',
      `Team lane: ${lane}`,
      `Authorized working directory: ${cwd}`,
      'Follow all repository instructions, including AGENTS.md and CLAUDE.md when present.',
      'Do not modify files, run shell commands, alter Git, connect to remote machines, or perform external side effects.',
      'Return findings, evidence paths, assumptions, and recommended next steps.',
    ];
  }

  return `${constraints.join('\n')}\n\nDelegated task:\n${prompt}`;
}

function runClaude(args) {
  return new Promise((resolve) => {
    let cwd;
    try {
      cwd = resolveWorkingDirectory(args.cwd);
    } catch (error) {
      resolve(textResult(error.message, true));
      return;
    }

    const mode = args.mode || 'read_only';
    const lane = args.lane || 'general';
    const permissionMode = mode === 'edit' ? 'acceptEdits' : 'dontAsk';
    const remoteReadOnly = mode === 'jetson_read_only';
    const tools = mode === 'edit'
      ? 'Read,Glob,Grep,Edit,Write,NotebookEdit'
      : remoteReadOnly ? 'Read,Glob,Grep,Bash' : 'Read,Glob,Grep';
    const timeoutMs = Math.min(Math.max(Number(args.timeout_seconds || 600) * 1000, 10_000), 600_000);
    const budget = Math.min(Math.max(Number(args.max_budget_usd || DEFAULT_BUDGET_USD), 0.01), 10);
    const executable = process.env.CLAUDE_CODE_EXECUTABLE || 'claude';
    const cliArgs = [
      '-p',
      '--output-format', 'json',
      '--permission-mode', permissionMode,
      '--tools', tools,
      '--max-budget-usd', String(budget),
      '--no-session-persistence',
    ];
    if (remoteReadOnly) {
      const helper = (process.env.JETSON_READONLY_HELPER || 'F:/slamibot_agent/.ai-workspace/mcp/jetson-readonly.cjs').replace(/\\/g, '/');
      cliArgs.push('--allowedTools', `Bash(node ${helper} *)`);
    }
    if (args.model) cliArgs.push('--model', args.model);

    const child = spawn(executable, cliArgs, {
      cwd,
      env: process.env,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';
    let settled = false;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => finish(textResult(`Failed to start Claude Code: ${error.message}`, true)));
    child.on('close', (code) => {
      let payload;
      try {
        payload = JSON.parse(stdout.trim());
      } catch {
        const details = [stdout.trim(), stderr.trim()].filter(Boolean).join('\n');
        finish(textResult(`Claude Code returned invalid JSON (exit ${code}).\n${details}`, true));
        return;
      }

      const resultText = typeof payload.result === 'string'
        ? payload.result
        : JSON.stringify(payload.result ?? payload, null, 2);
      if (code !== 0 || payload.is_error) {
        const errorText = payload.error || resultText || stderr.trim() || `Claude Code exited with ${code}`;
        finish(textResult(errorText, true));
        return;
      }

      finish({
        content: [{ type: 'text', text: resultText }],
        structuredContent: {
          session_id: payload.session_id || null,
          num_turns: payload.num_turns ?? null,
          duration_ms: payload.duration_ms ?? null,
          total_cost_usd: payload.total_cost_usd ?? null,
          permission_denials: payload.permission_denials || [],
          lane,
          max_concurrency: MAX_CONCURRENCY,
        },
        isError: false,
      });
    });

    const timer = setTimeout(() => {
      child.kill();
      finish(textResult(`Claude Code timed out after ${timeoutMs / 1000} seconds`, true));
    }, timeoutMs);

    child.stdin.end(buildPrompt(args.prompt, mode, cwd, lane), 'utf8');
  });
}
function drainQueue() {
  while (activeJobs < MAX_CONCURRENCY && pendingJobs.length > 0) {
    const job = pendingJobs.shift();
    activeJobs += 1;
    const queueWaitMs = Date.now() - job.enqueuedAt;
    runClaude(job.args)
      .then((result) => {
        result.structuredContent = {
          ...(result.structuredContent || {}),
          lane: job.args.lane || 'general',
          queue_wait_ms: queueWaitMs,
          max_concurrency: MAX_CONCURRENCY,
        };
        job.resolve(result);
      })
      .catch((error) => job.resolve(textResult(`Claude Code delegation failed: ${error.message}`, true)))
      .finally(() => {
        activeJobs -= 1;
        drainQueue();
      });
  }
}

function scheduleClaude(args) {
  return new Promise((resolve) => {
    pendingJobs.push({ args, resolve, enqueuedAt: Date.now() });
    drainQueue();
  });
}
const delegateTool = {
  name: 'delegate',
  title: 'Delegate to Claude Code',
  description: 'Delegate a bounded task to the locally installed Claude Code CLI. Use read_only by default, edit only for authorized local file changes, and jetson_read_only only for fixed allowlisted SSH inspection. BUILD/DEPLOY/DANGEROUS remote actions are not available.',
  inputSchema: {
    type: 'object',
    properties: {
      prompt: { type: 'string', description: 'Complete task, constraints, allowed paths, forbidden actions, and required validation/reporting.' },
      cwd: { type: 'string', description: 'Absolute authorized repository or test-directory path.' },
      mode: { type: 'string', enum: ['read_only', 'edit', 'jetson_read_only'], default: 'read_only', description: 'Use jetson_read_only only for fixed allowlisted SSH inspection. BUILD/DEPLOY remain task-authorized Codex operations.' },
      lane: { type: 'string', enum: ['general', 'frontend', 'backend', 'navigation'], default: 'general', description: 'Logical project lane used for queueing and concise handoff.' },
      model: { type: 'string', enum: ['sonnet', 'opus', 'haiku', 'fable'], description: 'Optional Claude Code model alias.' },
      timeout_seconds: { type: 'integer', minimum: 10, maximum: 600, default: 600 },
      max_budget_usd: { type: 'number', minimum: 0.01, maximum: 10, default: 2 },
    },
    required: ['prompt', 'cwd'],
    additionalProperties: false,
  },
  annotations: {
    readOnlyHint: false,
    destructiveHint: false,
    idempotentHint: false,
    openWorldHint: true,
  },
};

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on('line', async (line) => {
  if (!line.trim()) return;
  let request;
  try {
    request = JSON.parse(line);
  } catch {
    send({ jsonrpc: '2.0', id: null, error: { code: -32700, message: 'Parse error' } });
    return;
  }

  if (request.method === 'initialize') {
    send({
      jsonrpc: '2.0',
      id: request.id,
      result: {
        protocolVersion: request.params?.protocolVersion || '2025-06-18',
        capabilities: { tools: {} },
        serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
      },
    });
    return;
  }
  if (request.method === 'notifications/initialized') return;
  if (request.method === 'ping') {
    send({ jsonrpc: '2.0', id: request.id, result: {} });
    return;
  }
  if (request.method === 'tools/list') {
    send({ jsonrpc: '2.0', id: request.id, result: { tools: [delegateTool] } });
    return;
  }
  if (request.method === 'tools/call') {
    if (request.params?.name !== 'delegate') {
      send({ jsonrpc: '2.0', id: request.id, error: { code: -32602, message: 'Unknown tool' } });
      return;
    }
    const result = await scheduleClaude(request.params.arguments || {});
    send({ jsonrpc: '2.0', id: request.id, result });
    return;
  }

  if (request.id !== undefined) {
    send({ jsonrpc: '2.0', id: request.id, error: { code: -32601, message: 'Method not found' } });
  }
});

