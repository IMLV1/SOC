// Local by default; deployment must explicitly choose its binding interface.
process.env.HOSTNAME = process.env.SOC_BIND_HOST || "127.0.0.1";
require("../.next/standalone/server.js");
