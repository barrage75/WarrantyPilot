import ts from "typescript";
import { expect, it } from "vitest";
const sources = import.meta.glob("../**/*.tsx", { query: "?raw", import: "default", eager: true });
it("keeps user-facing JSX text and accessible names in translations", () => {
 const violations: string[] = [];
 for (const [path, source] of Object.entries(sources)) {
  if (path.endsWith(".test.tsx")) continue;
  const file = ts.createSourceFile(path, String(source), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  function visit(node: ts.Node) {
   if (ts.isJsxText(node) && /[\p{L}\p{N}]/u.test(node.text)) violations.push(path + ": " + node.text.trim());
   if (ts.isJsxAttribute(node) && ["aria-label", "title", "placeholder", "alt"].includes(node.name.getText(file)) && node.initializer && ts.isStringLiteral(node.initializer) && /[\p{L}\p{N}]/u.test(node.initializer.text)) violations.push(path + ": " + node.getText(file));
   ts.forEachChild(node, visit);
  }
  visit(file);
 }
 expect(violations).toEqual([]);
});
