import ts from "typescript";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { source } from "./source.census-D12";

// Follow only the requested export through barrels. Reading every barrel export
// would let an unrelated screen's explanation satisfy the current screen.
export function exportedSources(file: string, name: string, seen = new Set<string>()): ts.SourceFile[] {
  const key = `${file}:${name}`;
  if (seen.has(key)) return [];
  seen.add(key);
  const sf = source(file);
  for (const statement of sf.statements) {
    if (ts.isExportDeclaration(statement) && statement.moduleSpecifier && ts.isStringLiteral(statement.moduleSpecifier)) {
      const clause = statement.exportClause;
      const binding = clause && ts.isNamedExports(clause) ? clause.elements.find(item => item.name.text === name) : undefined;
      if (clause && !binding) continue;
      const child = modulePath(file, statement.moduleSpecifier.text);
      if (child) {
        const found = exportedSources(child, binding?.propertyName?.text ?? name, seen);
        if (found.length) return found;
      }
    }
    if ((ts.isFunctionDeclaration(statement) || ts.isClassDeclaration(statement)) && statement.name?.text === name) return [sf];
    if (ts.isVariableStatement(statement)) for (const item of statement.declarationList.declarations) {
      if (item.name.getText() !== name) continue;
      const lazy = item.initializer?.getText().match(/lazy\(.*import\(["']([^"']+)["']\).*default:\s*\w+\.(\w+)/s);
      const child = lazy && modulePath(file, lazy[1]);
      return child ? exportedSources(child, lazy![2], seen) : [sf];
    }
  }
  return [];
}
export function modulePath(from: string, specifier: string) {
  const base = resolve(dirname(from), specifier);
  return [base + ".tsx", base + ".ts", resolve(base, "index.ts"), resolve(base, "index.tsx")].find(existsSync);
}
