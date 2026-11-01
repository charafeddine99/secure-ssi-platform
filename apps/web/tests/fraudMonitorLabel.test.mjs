import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createServer } from "vite";

const webRoot = fileURLToPath(new URL("..", import.meta.url));
const server = await createServer({
  root: webRoot,
  configFile: fileURLToPath(new URL("../vite.config.ts", import.meta.url)),
  server: { middlewareMode: true },
  logLevel: "silent",
});

try {
  const { RiskStatusValue } = await server.ssrLoadModule("/src/pages/admin/RiskStatusValue.tsx");
  const renderValue = (value) => renderToStaticMarkup(
    React.createElement(RiskStatusValue, { as: "strong", value }),
  );

  assert.equal(
    renderValue("[DEMO LAB / SYNTHETIC]"),
    "<strong>[DEMO LAB / SYNTHETIC]</strong>",
    "The required synthetic-data marker must remain exact in rendered UI text.",
  );
  assert.equal(renderValue("NOT_TRAINED"), "<strong>Not Trained</strong>");
  assert.equal(renderValue(undefined), "<strong>Not reported</strong>");
  console.log("WP-09 Admin risk label SSR regression: 3 passed, 0 failed.");
} finally {
  await server.close();
}
