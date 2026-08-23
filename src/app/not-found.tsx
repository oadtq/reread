import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl px-6 py-24">
      <p className="kicker">Not found</p>
      <h1 className="mt-3 text-3xl font-medium tracking-tight">Not in the library</h1>
      <p className="mt-4 text-mute">That book or section is not on the shelf.</p>
      <Link href="/" className="btn btn-primary mt-8">
        Return to the library
      </Link>
    </div>
  );
}
