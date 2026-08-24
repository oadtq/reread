import { notFound } from "next/navigation";
import { BookArticle } from "@/components/book/article";
import { BookSpy, BookTopbar } from "@/components/book/book-reader";
import { headingsFromBody } from "@/components/book/page-rail";
import { Sidebar } from "@/components/book/sidebar";
import { imageDimensionsFromBody, loadCatalog, loadNav, loadPages } from "@/lib/book/load";
import { restorePositionScript } from "@/lib/book/progress";

type PageProps = {
  params: Promise<{ book: string }>;
};

export function generateStaticParams() {
  return loadCatalog().books.flatMap((book) => {
    try {
      loadNav(book.id);
      return [{ book: book.id }];
    } catch {
      return [];
    }
  });
}

export async function generateMetadata({ params }: PageProps) {
  const { book } = await params;
  try {
    const nav = loadNav(book);
    return { title: nav.title };
  } catch {
    return { title: "DeepRead" };
  }
}

export default async function BookHome({ params }: PageProps) {
  const { book } = await params;
  const found = loadCatalog().books.find((item) => item.id === book);
  if (!found?.startSlug) notFound();
  let nav;
  try {
    nav = loadNav(book);
  } catch {
    notFound();
  }
  const pages = loadPages(book);
  if (pages.length === 0) notFound();

  const headingsBySlug = Object.fromEntries(
    pages.map((page) => [page.slug, headingsFromBody(page.body, page.slug)]),
  );

  return (
    <div className="book-app" data-book={book}>
      <BookTopbar title={nav.title} />
      <div className="book-grid">
        <Sidebar bookId={book} tree={nav.tree} startSlug={found.startSlug} />
        <div
          className="book-main"
          id="book-scroll"
          data-book-id={book}
          data-start-slug={found.startSlug}
        >
          <div className="book-article">
            <div className="book-stack">
              {pages.map((page, index) => {
                const headings = headingsBySlug[page.slug] ?? [];
                const imageDimensions = imageDimensionsFromBody(page.body);
                const firstImage = page.body.match(/!\[[^\]]*\]\((\/books\/[^)]+)\)/);
                const eagerImage =
                  index === 0 &&
                  firstImage &&
                  firstImage.index !== undefined &&
                  page.body.slice(0, firstImage.index).split(/\s+/).length < 180
                    ? firstImage[1]
                    : undefined;
                const HeadingTag = page.level <= 2 ? "h1" : "h2";
                return (
                  <section
                    key={page.slug}
                    id={page.slug}
                    data-slug={page.slug}
                    data-title={page.title}
                    className="book-section"
                  >
                    <header className="reader-heading">
                      <p className="kicker reader-meta">
                        <span>Print p. {page.page}</span>
                        <span aria-hidden="true">·</span>
                        <span>
                          Section {index + 1} of {pages.length}
                        </span>
                      </p>
                      <HeadingTag>{page.title}</HeadingTag>
                    </header>
                    {page.body ? (
                      <div className="reader-body">
                        <BookArticle
                          body={page.body}
                          glossary={page.slug.includes("glossary")}
                          headings={headings}
                          imageDimensions={imageDimensions}
                          eagerImage={eagerImage}
                        />
                      </div>
                    ) : null}
                  </section>
                );
              })}
            </div>
          </div>
        </div>
      </div>
      <BookSpy bookId={book} startSlug={found.startSlug} />
      <script dangerouslySetInnerHTML={{ __html: restorePositionScript() }} />
    </div>
  );
}
