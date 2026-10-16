const { cpSync, existsSync } = require("node:fs");
const { resolve } = require("node:path");

const root = resolve(__dirname, "..");
cpSync(
  resolve(root, ".next/static"),
  resolve(root, ".next/standalone/.next/static"),
  { recursive: true },
);
if (existsSync(resolve(root, "public"))) {
  cpSync(resolve(root, "public"), resolve(root, ".next/standalone/public"), {
    recursive: true,
  });
}
