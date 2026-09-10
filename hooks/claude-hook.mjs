#!/usr/bin/env node
// Claude Code hook script (observe-only). Never blocks the agent:
// 2s self-timeout, all failures swallowed, loopback POST only.
//
// Install: add to ~/.claude/settings.json:
//   {"hooks": {"SessionStart": [{"hooks": [{"type": "command",
//     "command": "node /path/to/vibe-learning/hooks/claude-hook.mjs",
//     "timeout": 2}]}],
//     "PreToolUse": [...same...], "PostToolUse": [...same...],
//     "Stop": [...same...], "SessionEnd": [...same...]}}
// The hook event JSON arrives on stdin.
import http from "http";

const PORT = process.env.VIBE_LEARNING_PORT || 8765;

function main() {
  let raw = "";
  process.stdin.setEncoding("utf8");
  const killer = setTimeout(() => process.exit(0), 2000);
  process.stdin.on("data", (c) => { raw += c; });
  process.stdin.on("end", () => {
    clearTimeout(killer);
    let payload = {};
    try { payload = JSON.parse(raw || "{}"); } catch { process.exit(0); }
    const body = JSON.stringify(payload);
    const req = http.request({
      host: "127.0.0.1", port: PORT, path: "/hooks/claude",
      method: "POST", headers: { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) },
      timeout: 1500,
    }, (res) => { res.resume(); res.on("end", () => process.exit(0)); });
    req.on("timeout", () => { req.destroy(); process.exit(0); });
    req.on("error", () => process.exit(0));
    req.end(body);
    setTimeout(() => process.exit(0), 2000).unref();
  });
}

main();
