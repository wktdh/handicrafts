import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";

// Prefer the repository virtual environment when it exists. This keeps the
// backend test command aligned with the dependencies used by local API and
// E2E runs, while remaining usable in CI systems that provide Python globally.
const venvPython = process.platform === "win32"
  ? "venv/Scripts/python.exe"
  : "venv/bin/python";
const python = existsSync(venvPython)
  ? venvPython
  : process.env.PYTHON || "python";
const result = spawnSync(
  python,
  ["-m", "unittest", "discover", "-s", "database/tests", "-v"],
  { stdio: "inherit", shell: process.platform === "win32" && !existsSync(venvPython) },
);

if (result.error) throw result.error;
process.exit(result.status ?? 1);
