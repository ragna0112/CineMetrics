import type { Metadata } from "next";
import Link from "next/link";
import { Clapperboard, ArrowUpRight } from "lucide-react";
import "./globals.css";
export const metadata: Metadata = {
  title: "CineMetrics · Beyond the box office",
  description: "Explore movie popularity with real daily TMDB snapshots.",
};
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <a className="skip" href="#main">
          Skip to content
        </a>
        <header>
          <Link href="/" className="brand">
            <span className="brand-icon">
              <Clapperboard size={21} />
            </span>
            Cine<span>Metrics</span>
          </Link>
          <nav aria-label="Main navigation">
            <Link href="/">Overview</Link>
            <Link href="/discover">Discover</Link>
            <Link href="/rising">
              Rising movies <ArrowUpRight size={14} />
            </Link>
          </nav>
          <span className="source">
            <i /> Powered by TMDB
          </span>
        </header>
        <main id="main">{children}</main>
        <footer>
          <div>
            <Link href="/" className="brand small">
              Cine<span>Metrics</span>
            </Link>
            <p>A closer look at what the world is watching.</p>
          </div>
          <div aria-label="Credits">
            <a
              href="https://www.themoviedb.org/"
              target="_blank"
              rel="noreferrer"
              className="tmdb"
            >
              <img
                src="https://www.themoviedb.org/assets/2/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg"
                alt="TMDB"
                width="90"
                height="12"
              />
            </a>
            <p>
              This product uses the TMDB API but is not endorsed or certified by
              TMDB.
            </p>
            <p>
              Popularity is a TMDB-specific score, not views or revenue.
              Rankings cover our collected dataset.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
