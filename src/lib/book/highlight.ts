import type { LanguageFn } from "highlight.js";
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import csharp from "highlight.js/lib/languages/csharp";
import css from "highlight.js/lib/languages/css";
import diff from "highlight.js/lib/languages/diff";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import protobuf from "highlight.js/lib/languages/protobuf";
import python from "highlight.js/lib/languages/python";
import ruby from "highlight.js/lib/languages/ruby";
import sql from "highlight.js/lib/languages/sql";
import thrift from "highlight.js/lib/languages/thrift";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

const cypher: LanguageFn = (engine) => ({
  name: "Cypher",
  aliases: ["cypher"],
  case_insensitive: true,
  keywords: {
    keyword:
      "create match merge delete detach set remove return with unwind foreach where optional order by skip limit asc desc distinct as union all and or xor not in is unique constraint index on drop call yield case when then else end starts ends contains load csv from",
    literal: "true false null",
  },
  contains: [
    engine.QUOTE_STRING_MODE,
    engine.APOS_STRING_MODE,
    engine.C_LINE_COMMENT_MODE,
    engine.C_NUMBER_MODE,
    { className: "symbol", begin: /:[A-Za-z_][A-Za-z0-9_]*/ },
  ],
});

const turtle: LanguageFn = (engine) => ({
  name: "Turtle",
  aliases: ["turtle", "n3"],
  contains: [
    engine.HASH_COMMENT_MODE,
    engine.QUOTE_STRING_MODE,
    engine.C_NUMBER_MODE,
    { className: "keyword", begin: /@(?:prefix|base)\b/i },
    { className: "symbol", begin: /(?:[A-Za-z_][\w.-]*:|_:)[A-Za-z_][\w.-]*/ },
    { className: "string", begin: /<[^>]*>/ },
  ],
});

const sparql: LanguageFn = (engine) => ({
  name: "SPARQL",
  aliases: ["sparql"],
  case_insensitive: true,
  keywords: {
    keyword:
      "prefix select distinct reduced where optional filter union graph order by asc desc limit offset bind values service minus exists not as in",
    literal: "true false",
  },
  contains: [
    engine.HASH_COMMENT_MODE,
    engine.QUOTE_STRING_MODE,
    engine.C_NUMBER_MODE,
    { className: "symbol", begin: /[?$][A-Za-z_][\w]*/ },
    { className: "string", begin: /<[^>]*>/ },
  ],
});

const datalog: LanguageFn = (engine) => ({
  name: "Datalog",
  aliases: ["datalog"],
  contains: [
    engine.QUOTE_STRING_MODE,
    engine.APOS_STRING_MODE,
    engine.HASH_COMMENT_MODE,
    engine.C_LINE_COMMENT_MODE,
    { className: "keyword", begin: /(?:not\b|:-)/ },
    { className: "title.function", begin: /[a-z][A-Za-z0-9_]*(?=\s*\()/ },
  ],
});

const ALIASES: Record<string, string> = {
  js: "javascript",
  node: "javascript",
  ts: "javascript",
  py: "python",
  rb: "ruby",
  "c++": "cpp",
  cxx: "cpp",
  cc: "cpp",
  cuda: "cpp",
  sh: "bash",
  shell: "bash",
  yml: "yaml",
  proto: "protobuf",
  avro: "json",
  n3: "turtle",
  rdf: "xml",
};

let registered = false;

function registerLanguages() {
  if (registered) return;
  hljs.registerLanguage("bash", bash);
  hljs.registerLanguage("c", c);
  hljs.registerLanguage("cpp", cpp);
  hljs.registerLanguage("csharp", csharp);
  hljs.registerLanguage("css", css);
  hljs.registerLanguage("cypher", cypher);
  hljs.registerLanguage("diff", diff);
  hljs.registerLanguage("datalog", datalog);
  hljs.registerLanguage("ini", ini);
  hljs.registerLanguage("java", java);
  hljs.registerLanguage("javascript", javascript);
  hljs.registerLanguage("json", json);
  hljs.registerLanguage("protobuf", protobuf);
  hljs.registerLanguage("python", python);
  hljs.registerLanguage("ruby", ruby);
  hljs.registerLanguage("sparql", sparql);
  hljs.registerLanguage("sql", sql);
  hljs.registerLanguage("thrift", thrift);
  hljs.registerLanguage("turtle", turtle);
  hljs.registerLanguage("xml", xml);
  hljs.registerLanguage("yaml", yaml);
  registered = true;
}

export function highlightCode(source: string, language?: string): string | null {
  if (!language) return null;
  registerLanguages();
  const resolved = ALIASES[language.toLowerCase()] ?? language.toLowerCase();
  if (!hljs.getLanguage(resolved)) return null;
  try {
    return hljs.highlight(source, { language: resolved, ignoreIllegals: true }).value;
  } catch {
    return null;
  }
}
