import type { ReactNode } from "react";
import Image from "next/image";
import type { Components } from "react-markdown";
import Markdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import { CodeBlock } from "@/components/book/code-block";
import { highlightCode } from "@/lib/book/highlight";
import type { PageHeading } from "@/lib/book/headings";
import type { ImageDimensions } from "@/lib/book/load";

type HastNode = {
  type?: string;
  tagName?: string;
  value?: string;
  children?: HastNode[];
  properties?: Record<string, unknown>;
  position?: { start?: { line?: number } };
};

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  return "";
}

/** Reads the untouched source text of a markdown node straight from the AST. */
function rawText(node?: HastNode): string {
  if (!node) return "";
  if (node.type === "text") return node.value ?? "";
  return (node.children ?? []).map(rawText).join("");
}

function classList(node?: HastNode): string[] {
  const value = node?.properties?.className;
  if (Array.isArray(value)) return value.map(String);
  if (typeof value === "string") return value.split(/\s+/);
  return [];
}

function containsTag(node: HastNode | undefined, tag: string): boolean {
  if (!node?.children) return false;
  return node.children.some((child) => child.tagName === tag || containsTag(child, tag));
}

function paragraph({ children, node }: { children?: ReactNode; node?: unknown }, glossary: boolean) {
  if (containsTag(node as HastNode | undefined, "img")) {
    return <>{children}</>;
  }
  if (glossary) {
    const text = textOf(children);
    const index = text.indexOf(":");
    if (index > 1 && index < 72 && /^[A-Z0-9]/.test(text) && text.slice(index + 1).trim().length > 12) {
      return (
        <p className="term">
          <dfn>{text.slice(0, index)}</dfn>
          <span>{text.slice(index + 1).trim()}</span>
        </p>
      );
    }
  }
  return <p>{children}</p>;
}

export function BookArticle({
  body,
  glossary = false,
  headings,
  imageDimensions,
  eagerImage,
}: {
  body: string;
  glossary?: boolean;
  headings: PageHeading[];
  imageDimensions: ImageDimensions;
  eagerImage?: string;
}) {
  if (!body) return null;

  const idAt = (node: unknown, level: number) => {
    const line = (node as HastNode | undefined)?.position?.start?.line;
    return headings.find((heading) => heading.line === line && heading.level === level)?.id;
  };

  const components: Components = {
    p(props) {
      return paragraph(props, glossary);
    },
    h2({ children, node }) {
      const id = idAt(node, 2);
      return (
        <h2 id={id} data-title={textOf(children)}>
          {id ? (
            <a href={`#${id}`} className="heading-anchor" aria-label="Link to this heading">
              #
            </a>
          ) : null}
          {children}
        </h2>
      );
    },
    h3({ children, node }) {
      const id = idAt(node, 3);
      return (
        <h3 id={id} data-title={textOf(children)}>
          {id ? (
            <a href={`#${id}`} className="heading-anchor" aria-label="Link to this heading">
              #
            </a>
          ) : null}
          {children}
        </h3>
      );
    },
    img({ src, alt }) {
      if (!src || typeof src !== "string") return null;
      const size = imageDimensions[src];
      const caption = alt?.trim();
      const portrait = size && size.height / size.width > 1.2;
      return (
        <figure className={`book-figure${portrait ? " book-figure-portrait" : ""}`}>
          <a
            href={src}
            target="_blank"
            rel="noreferrer"
            className="figure-zoom"
            aria-label={`Open full-size figure${caption ? `: ${caption}` : ""}`}
          >
            {size ? (
              <Image
                src={src}
                alt={caption ?? "Book figure"}
                width={size.width}
                height={size.height}
                sizes="(max-width: 860px) calc(100vw - 2rem), 780px"
                loading={src === eagerImage ? "eager" : "lazy"}
              />
            ) : (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={src}
                alt={caption ?? "Book figure"}
                loading={src === eagerImage ? "eager" : "lazy"}
                decoding="async"
              />
            )}
          </a>
          {caption ? <figcaption>{caption}</figcaption> : null}
        </figure>
      );
    },
    table({ children }) {
      return (
        <div className="table-scroll" tabIndex={0} role="region" aria-label="Scrollable table">
          <table>{children}</table>
        </div>
      );
    },
    pre({ children, node }) {
      const codeNode = (node as HastNode | undefined)?.children?.find((child) => child.tagName === "code");
      const language =
        classList(codeNode)
          .find((name) => name.startsWith("language-"))
          ?.replace("language-", "") ?? "";
      return (
        <CodeBlock language={language} source={rawText(codeNode).replace(/\n$/, "")}>
          {children}
        </CodeBlock>
      );
    },
    code({ className, children }) {
      const language = /language-([\w+-]+)/.exec(className ?? "")?.[1];
      if (!language) {
        return <code>{children}</code>;
      }
      const source = textOf(children).replace(/\n$/, "");
      const html = highlightCode(source, language);
      return html ? (
        <code className={className} dangerouslySetInnerHTML={{ __html: html }} />
      ) : (
        <code className={className}>{source}</code>
      );
    },
  };

  return (
    <div className="book-prose">
      <Markdown
        remarkPlugins={[remarkGfm, [remarkMath, { singleDollarTextMath: false }]]}
        rehypePlugins={[rehypeKatex]}
        components={components}
      >
        {body}
      </Markdown>
    </div>
  );
}
