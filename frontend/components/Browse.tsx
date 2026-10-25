"use client";
import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  ArrowLeft,
  ArrowRight,
  Search,
  SlidersHorizontal,
  Film,
  Star,
  Activity,
  Database,
  Clock,
  TrendingUp,
} from "lucide-react";
import Card from "./Card";
import { Movie, Summary, request, num } from "./data";
export default function Browse({
  mode,
}: {
  mode: "overview" | "discover" | "rising";
}) {
  const [summary, setSummary] = useState<Summary | null>(null),
    [genres, setGenres] = useState<{ id: number; name: string }[]>([]),
    [movies, setMovies] = useState<Movie[]>([]),
    [total, setTotal] = useState(0),
    [page, setPage] = useState(1),
    [q, setQ] = useState(""),
    [genre, setGenre] = useState(""),
    [year, setYear] = useState(""),
    [votes, setVotes] = useState("0"),
    [sort, setSort] = useState("popularity"),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0),
    [dates, setDates] = useState("");
  useEffect(() => {
    const c = new AbortController();
    Promise.all([
      request<Summary>("/summary", c.signal),
      request<{ id: number; name: string }[]>("/genres", c.signal),
    ])
      .then(([s, g]) => {
        setSummary(s);
        setGenres(g);
      })
      .catch(() => {});
    return () => c.abort();
  }, [retry]);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setError("");
    const timer = setTimeout(async () => {
      try {
        if (mode === "rising") {
          const r = await request<{
            items: Movie[];
            from_day: string | null;
            to_day: string | null;
          }>("/rising", c.signal);
          setMovies(r.items);
          setTotal(r.items.length);
          setDates(
            r.from_day
              ? `${r.from_day} → ${r.to_day} · UTC`
              : "Waiting for a second collection day",
          );
        } else {
          const p = new URLSearchParams({
            page: String(page),
            q,
            sort,
            min_votes: votes || "0",
            ...(genre ? { genre } : {}),
            ...(year ? { year } : {}),
          });
          const r = await request<{ items: Movie[]; total: number }>(
            `/movies?${p}`,
            c.signal,
          );
          setMovies(r.items);
          setTotal(r.total);
        }
      } catch (e) {
        if (!c.signal.aborted) setError((e as Error).message);
      } finally {
        if (!c.signal.aborted) setLoading(false);
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      c.abort();
    };
  }, [mode, page, q, genre, year, votes, sort, retry]);
  const filter = (setter: (s: string) => void, value: string) => {
    setter(value);
    setPage(1);
  };
  return (
    <>
      <section className="intro">
        <div className="eyebrow">
          <span /> THE MOVIE INTELLIGENCE PLATFORM
        </div>
        <div className="intro-row">
          <div>
            <h1>
              {mode === "rising" ? (
                "Catch the next wave."
              ) : mode === "discover" ? (
                "Find your next obsession."
              ) : (
                <>
                  Movies move.
                  <br />
                  Stay <em>ahead of the curve.</em>
                </>
              )}
            </h1>
            <p>
              {mode === "rising"
                ? "The biggest popularity gains across comparable daily snapshots."
                : "Discover what’s popular. Follow the momentum. See the bigger picture."}
            </p>
          </div>
          <div className="intro-note">
            <Activity size={32} />
            <span>
              Real movies.
              <br />
              Real data. Daily perspective.
            </span>
          </div>
        </div>
        <div className="refresh">
          <Clock size={13} />
          {summary?.last_refresh
            ? `Last successful refresh: ${new Date(summary.last_refresh).toLocaleString()}`
            : "No successful refresh yet"}
          <span className="utc">DAILY SNAPSHOTS · UTC</span>
        </div>
      </section>
      <section className="stats" aria-label="Dataset summary">
        {[
          {
            label: "Movies tracked",
            value: summary ? num(summary.movies, 0) : "—",
            sub: "In our collected dataset",
            Icon: Film,
          },
          {
            label: "Average rating",
            value: summary ? num(summary.average_rating, 2) : "—",
            sub: "Unweighted · out of 10",
            Icon: Star,
          },
          {
            label: "Average popularity",
            value: summary ? num(summary.average_popularity) : "—",
            sub: "TMDB popularity score",
            Icon: TrendingUp,
          },
          {
            label: "Votes recorded",
            value: summary ? num(summary.total_votes, 0) : "—",
            sub: "Latest snapshot per movie",
            Icon: Database,
          },
        ].map(({ label, value, sub, Icon }) => (
          <div className="stat" key={label}>
            <div>
              {label}
              <Icon size={16} />
            </div>
            <strong>{value}</strong>
            <p>{sub}</p>
          </div>
        ))}
      </section>
      <section className="collection">
        <div className="section-heading">
          <div>
            <div className="eyebrow muted">
              {mode === "rising" ? "MOMENTUM WATCH" : "THE CURRENT PICTURE"}
            </div>
            <h2>
              {mode === "rising" ? "On the rise" : "Explore the rankings"}
              <span className="pill">{num(total, 0)} movies</span>
            </h2>
          </div>
          <span className="coverage">
            {mode === "rising" ? dates : "Ranked within our collected dataset"}{" "}
            <ArrowUpRight size={14} />
          </span>
        </div>
        {mode !== "rising" && (
          <div className="filters">
            <label className="search">
              <Search size={17} />
              <input
                aria-label="Search movies"
                placeholder="Search movies by title…"
                value={q}
                onChange={(e) => filter(setQ, e.target.value)}
              />
            </label>
            <label>
              <span>Genre</span>
              <select
                value={genre}
                onChange={(e) => filter(setGenre, e.target.value)}
              >
                <option value="">All genres</option>
                {genres.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Release year</span>
              <input
                aria-label="Release year"
                type="number"
                min="1870"
                max="2200"
                placeholder="All years"
                value={year}
                onChange={(e) => filter(setYear, e.target.value)}
              />
            </label>
            <label>
              <span>Minimum votes</span>
              <select
                value={votes}
                onChange={(e) => filter(setVotes, e.target.value)}
              >
                {[0, 100, 500, 1000, 5000].map((v) => (
                  <option key={v} value={v}>
                    {v === 0
                      ? "Any vote count"
                      : `${v.toLocaleString()}+ votes`}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Sort by</span>
              <select
                value={sort}
                onChange={(e) => filter(setSort, e.target.value)}
              >
                <option value="popularity">Popularity</option>
                <option value="rating">Rating</option>
                <option value="release_date">Release date</option>
              </select>
            </label>
          </div>
        )}
        <div aria-live="polite">
          {loading ? (
            <div className="movie-grid">
              {Array.from({ length: 6 }, (_, i) => (
                <div className="skeleton" key={i} />
              ))}
            </div>
          ) : error ? (
            <div className="empty">
              <Database size={36} />
              <h3>We couldn’t load the collection</h3>
              <p>{error}</p>
              <button onClick={() => setRetry(retry + 1)}>
                Try again <ArrowRight size={16} />
              </button>
            </div>
          ) : movies.length === 0 ? (
            <div className="empty">
              <Film size={38} />
              <h3>
                {mode === "rising"
                  ? "Momentum takes a little time."
                  : summary?.movies
                    ? "No movies match these filters."
                    : "Your collection starts here."}
              </h3>
              <p>
                {mode === "rising"
                  ? "Collect data on at least two UTC days. Only movies present on both comparison dates with a positive change will appear."
                  : summary?.movies
                    ? "Try another title or broaden your filters."
                    : "Configure your TMDB token and run the ingestion CLI to bring real movie data into CineMetrics."}
              </p>
              {mode !== "rising" && (
                <button
                  onClick={() => {
                    setQ("");
                    setGenre("");
                    setYear("");
                    setVotes("0");
                    setPage(1);
                  }}
                >
                  <SlidersHorizontal size={15} /> Reset filters
                </button>
              )}
            </div>
          ) : (
            <div className="movie-grid">
              {movies.map((m, i) => (
                <Card movie={m} rank={(page - 1) * 12 + i + 1} key={m.id} />
              ))}
            </div>
          )}
        </div>
        {mode !== "rising" && total > 0 && !loading && !error && (
          <div className="pagination">
            <span>
              Showing {(page - 1) * 12 + 1}–{Math.min(page * 12, total)} of{" "}
              {total} movies
            </span>
            <div>
              <button
                aria-label="Previous page"
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                <ArrowLeft size={16} />
              </button>
              <span>
                Page {page} of {Math.ceil(total / 12)}
              </span>
              <button
                aria-label="Next page"
                disabled={page * 12 >= total}
                onClick={() => setPage(page + 1)}
              >
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}
      </section>
      <aside className="data-note">
        <Activity size={19} />
        <div>
          <strong>A snapshot, not the whole story.</strong>
          <p>
            We collect TMDB’s popular movies daily. History starts with our
            first collection
            {summary?.first_day ? ` on ${summary.first_day}` : ""}. Scores
            reflect each movie’s latest stored snapshot; collection dates may
            differ. Missing values stay missing.
          </p>
        </div>
        <span>
          BUILT ON DATA.
          <br />
          DRIVEN BY CURIOSITY.
        </span>
      </aside>
    </>
  );
}
