"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

const LABELS: Record<string, string> = {
  bash: "shell",
  sh: "shell",
  shell: "shell",
  js: "javascript",
  ts: "typescript",
  py: "python",
  rb: "ruby",
  yml: "yaml",
  "c++": "c++",
  cpp: "c++",
  cuda: "cuda",
  proto: "protobuf",
  csharp: "c#",
};

export function CodeBlock({
  language,
  source,
  children,
}: {
  language: string;
  source: string;
  children: ReactNode;
}) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  useEffect(() => () => clearTimeout(timer.current), []);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(source);
    } catch {
      return;
    }
    setCopied(true);
    clearTimeout(timer.current);
    timer.current = setTimeout(() => setCopied(false), 1600);
  };

  const label = LABELS[language.toLowerCase()] ?? language;

  return (
    <div className="code-block" data-lang={language}>
      <div className="code-head">
        <span className="code-lang">{label || "code"}</span>
        <button type="button" className="code-copy" onClick={copy} data-copied={copied ? "true" : undefined}>
          {copied ? "Copied" : "Copy"}
        </button>
      </div>
      <div className="code-scroll">
        <pre>{children}</pre>
      </div>
    </div>
  );
}
