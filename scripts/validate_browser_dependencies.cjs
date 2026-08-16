#!/usr/bin/env node

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const jspdfPath = path.join(
    root,
    "resources/vendor/jspdf-4.2.1.umd.min.js"
);
const fontPath = path.join(root, "resources/Caladea-Regular-normal.js");

const { jsPDF } = require(jspdfPath);
assert.equal(typeof jsPDF, "function", "vendored jsPDF does not export jsPDF");

const fontContext = {};
vm.createContext(fontContext);
vm.runInContext(fs.readFileSync(fontPath, "utf8"), fontContext, {
    filename: fontPath,
});
assert.equal(typeof fontContext.font, "string", "bundled PDF font is unavailable");
assert.ok(fontContext.font.length > 1000, "bundled PDF font is unexpectedly small");

const pdf = new jsPDF({ unit: "mm", format: "a4" });
pdf.addFileToVFS("Caladea-Regular-normal.ttf", fontContext.font);
pdf.addFont("Caladea-Regular-normal.ttf", "Caladea-Regular", "normal");
pdf.setFont("Caladea-Regular");
pdf.text("Svoz odpadu Litovel – bezpečnostní test", 10, 20);

const output = Buffer.from(pdf.output("arraybuffer"));
assert.ok(output.length > 1000, "jsPDF produced an unexpectedly small document");
assert.equal(output.subarray(0, 5).toString("ascii"), "%PDF-", "invalid PDF header");
assert.ok(output.includes(Buffer.from("%%EOF")), "invalid PDF trailer");

console.log(`validated jsPDF 4.2.1 with bundled font (${output.length} bytes)`);
