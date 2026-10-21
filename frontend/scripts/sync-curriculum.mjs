import { readFile, writeFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";

// Export exactly this public training document, never the backend fixture tree.
const source = new URL("../../backend/fixtures/learning/curriculum-v1.json", import.meta.url);
const destination = new URL("../public/learning/curriculum-v1.json", import.meta.url);
const content = await readFile(source, "utf8");
const curriculum = JSON.parse(content);
if (curriculum.purpose !== "training" || curriculum.content_status !== "draft_for_testing") {
  throw new Error("Only draft training content may be exported to the public preview.");
}
if (process.argv.includes("--check")) {
  if (await readFile(destination, "utf8") !== content) {
    throw new Error("Public curriculum is stale. Run node scripts/sync-curriculum.mjs from frontend/.");
  }
} else {
  await mkdir(new URL("../public/learning/", import.meta.url), { recursive: true });
  await writeFile(destination, content, "utf8");
}
console.log(`Public training curriculum ${process.argv.includes("--check") ? "verified" : "exported"}: ${fileURLToPath(destination)}`);
