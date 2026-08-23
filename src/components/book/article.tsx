import type { ReactNode } from "react";
import Image from "next/image";
import type { Components } from "react-markdown";
import Markdown from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import type { ImageDimensions } from "@/lib/book/load";
import type { PageHeading } from "@/components/book/page-rail";

type MdNode = { tagName?: string; children?: MdNode[] };
type PositionedNode = { position?: { start?: { line?: number } } };

function textOf(node: ReactNode): string {
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(textOf).join("");
  return "";
}

function containsTag(node: MdNode | undefined, tag: string): boolean {
  if (!node?.children) return false;
  return node.children.some((child) => child.tagName === tag || containsTag(child, tag));
}

function paragraph({ children, node }: { children?: ReactNode; node?: unknown }, glossary: boolean) {
  if (containsTag(node as MdNode | undefined, "img")) {
    return <>{children}</>;
  }
  if (glossary) {
    const text = textOf(children);
    const index = text.indexOf(":");
    if (index > 1 && index < 72 && /^[A-Z0-9]/.test(text) && text.slice(index + 1).trim().length > 12) {
      return (
        <p className="term">
          <dfn>{text.slice(0, index)}</dfn>
          {text.slice(index + 1)}
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
  const components: Components = {
    p(props) {
      return paragraph(props, glossary);
    },
    h2({ children, node }) {
      const line = (node as PositionedNode | undefined)?.position?.start?.line;
      const id = headings.find((heading) => heading.line === line)?.id;
      return <h2 id={id}>{children}</h2>;
    },
    img({ src, alt }) {
      if (!src || typeof src !== "string") return null;
      const size = imageDimensions[src];
      const caption = alt?.trim();
      return (
        <figure className={`book-figure${size && size.height / size.width > 1.2 ? " book-figure-portrait" : ""}`}>
          <a href={src} target="_blank" rel="noreferrer" className="figure-zoom" aria-label={`Open full-size figure${caption ? `: ${caption}` : ""}`}>
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
              <img src={src} alt={caption ?? "Book figure"} loading={src === eagerImage ? "eager" : "lazy"} decoding="async" />
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
