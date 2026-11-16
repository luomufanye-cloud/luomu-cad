#!/usr/bin/env node
/**
 * Luomu CAD skill installer.
 *
 *   npx github:luomufanye-cloud/luomu-cad --target claude
 *
 * What it does:
 *   - clones (or fast-forwards) this repository into an existing agent skills directory
 *   - never deletes anything; a foreign directory is refused, not overwritten
 *
 * What it deliberately does NOT do:
 *   - it does not write MCP config into your agent settings. Each host uses a
 *     different format, and guessing would risk clobbering your other servers.
 *     Run scripts/run.ps1 -Action verify afterwards; it generates
 *     runtime/mcp-config.json for you to merge by hand.
 *   - it does not install Python, uv or project dependencies.
 *   - it does not touch AutoCAD.
 */

import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const REPO = "https://github.com/luomufanye-cloud/luomu-cad.git";
const DIR_NAME = "luomu-cad";

/** skill roots are resolved from the home directory, never hardcoded. */
const TARGETS = {
  claude: ".claude/skills",
  codex: ".codex/skills",
  cursor: ".cursor/skills",
  codebuddy: ".codebuddy/skills",
  agents: ".agents/skills",
};

const argv = process.argv.slice(2);
const has = (f) => argv.includes(f);
const valueOf = (f) => {
  const i = argv.indexOf(f);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith("--") ? argv[i + 1] : null;
};

const dryRun = has("--dry-run");
const forceReinstall = has("--force-reinstall");
const explicitTarget = valueOf("--target");

if (has("--help") || has("-h")) {
  console.log(`
Luomu CAD skill installer

  npx github:luomufanye-cloud/luomu-cad --target claude

Options
  --target a,b        install into these hosts (${Object.keys(TARGETS).join(", ")}, or "all")
  --dry-run           print planned actions without writing anything
  --force-reinstall   rename a foreign existing directory to .bak-<timestamp> first
  --help              show this message

Without --target, only hosts whose skills directory already exists are used.
If none exists, nothing is created and you are asked to pass --target.

Afterwards, in the installed directory:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run.ps1 -Action verify
`);
  process.exit(0);
}

const log = (m) => console.log(m);
const warn = (m) => console.log(`  ! ${m}`);
const run = (cmd, args, opts = {}) => {
  if (dryRun) {
    log(`  [dry-run] ${cmd} ${args.join(" ")}`);
    return "";
  }
  return execFileSync(cmd, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], ...opts });
};

function gitAvailable() {
  try {
    execFileSync("git", ["--version"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

/** true when the directory is a checkout of this project. */
function isOurCheckout(dir) {
  if (!fs.existsSync(path.join(dir, "SKILL.md"))) return false;
  try {
    const url = execFileSync("git", ["-C", dir, "remote", "get-url", "origin"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
    return url.includes("luomu-cad");
  } catch {
    return false;
  }
}

function selectHosts() {
  if (explicitTarget) {
    if (explicitTarget === "all") return Object.keys(TARGETS);
    const names = explicitTarget.split(",").map((s) => s.trim()).filter(Boolean);
    const unknown = names.filter((n) => !TARGETS[n]);
    if (unknown.length) {
      console.error(`Unknown target: ${unknown.join(", ")}`);
      console.error(`Known targets: ${Object.keys(TARGETS).join(", ")}, all`);
      process.exit(1);
    }
    return names;
  }
  return Object.keys(TARGETS).filter((n) => fs.existsSync(path.join(os.homedir(), TARGETS[n])));
}

function installOne(host) {
  const root = path.join(os.homedir(), TARGETS[host]);
  const dest = path.join(root, DIR_NAME);
  log(`\n[${host}]`);
  log(`  skills root: ${root}`);

  if (!fs.existsSync(root)) {
    if (!explicitTarget) {
      warn("skills root missing, skipped");
      return "skipped";
    }
    warn("skills root missing; creating it because --target was explicit");
    if (!dryRun) fs.mkdirSync(root, { recursive: true });
  }

  if (fs.existsSync(dest)) {
    if (isOurCheckout(dest)) {
      log("  existing checkout found, fast-forwarding");
      try {
        run("git", ["-C", dest, "pull", "--ff-only"]);
        log("  updated");
        return "updated";
      } catch (e) {
        warn("fast-forward failed; nothing was deleted or reset");
        warn(String(e.message).split("\n")[0]);
        warn("resolve it manually, or re-run with --force-reinstall");
        return "failed";
      }
    }

    if (!forceReinstall) {
      warn("destination exists but is not a checkout of this repository");
      warn("refusing to touch it. Move it yourself, or pass --force-reinstall");
      warn(`destination: ${dest}`);
      return "refused";
    }

    const backup = `${dest}.bak-${new Date().toISOString().replace(/[:.]/g, "-")}`;
    warn(`renaming existing directory to ${path.basename(backup)} (not deleting)`);
    if (!dryRun) fs.renameSync(dest, backup);
  }

  log(`  cloning ${REPO}`);
  try {
    run("git", ["clone", "--depth", "1", REPO, dest]);
  } catch (e) {
    warn("git clone failed");
    warn(String(e.message).split("\n")[0]);
    warn("if your network blocks git, download the repository ZIP and unzip it to this path instead");
    return "failed";
  }
  log("  installed");
  return "installed";
}

function main() {
  log("Luomu CAD skill installer");
  if (dryRun) log("(dry-run: no files will be written)");

  if (!gitAvailable()) {
    console.error("\ngit was not found on PATH. Install git, or unzip the repository manually.");
    process.exit(1);
  }

  const hosts = selectHosts();
  if (!hosts.length) {
    console.error("\nNo existing skills directory found, so nothing was installed.");
    console.error("Pass --target explicitly, for example: --target claude");
    process.exit(1);
  }

  const results = {};
  for (const h of hosts) results[h] = installOne(h);

  log("\n--- summary ---");
  for (const [h, r] of Object.entries(results)) log(`  ${h}: ${r}`);

  const ok = Object.entries(results).filter(([, r]) => ["installed", "updated"].includes(r));
  if (ok.length) {
    log("\nNext steps (the installer does not run these for you):");
    for (const [h] of ok) {
      const dest = path.join(os.homedir(), TARGETS[h], DIR_NAME);
      log(`\n  ${h}: ${dest}`);
      log("    1. reload skills in your agent so it reads SKILL.md");
      log("    2. powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\run.ps1 -Action verify");
      log("    3. expect exit code 0 and ok=true; checks artifact_hashes / dxf_readback / preview_file = PASS");
      log("    4. to use MCP tools, merge the generated runtime/mcp-config.json entry yourself");
    }
    log("\n  Offline DXF, geometry checks and knowledge cards do not need AutoCAD.");
  }

  if (Object.values(results).some((r) => r === "failed" || r === "refused")) process.exitCode = 1;
}

main();
