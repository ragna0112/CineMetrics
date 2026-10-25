"use client";
import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Star, ExternalLink } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";
import Poster from "@/components/Poster";
import { Movie, num, request } from "@/components/data";
type Point = { day: string; popularity: number | null; rating: number | null };
export default function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [movie, setMovie] = useState<Movie | null>(null),
    [history, setHistory] = useState<Point[]>([]),
    [error, setError] = useState(""),
    [retry, setRetry] = useState(0);
  useEffect(() => {
    const c = new AbortController();
    setError("");
    Promise.all([
      request<Movie>(`/movies/${id}`, c.signal),
      request<Point[]>(`/movies/${id}/history`, c.signal),
    ])
      .then(([m, h]) => {
        setMovie(m);
        setHistory(h);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [id, retry]);
  if (error)
    return (
      <div className="empty">
        <h1>Movie unavailable</h1>
        <p>{error}</p>
        <button onClick={() => setRetry(retry + 1)}>Try again</button>
        <Link href="/discover">Back to discovery</Link>
      </div>
    );
  if (!movie)
    return (
      <div className="empty" role="status">
        Loading movie and daily history…
      </div>
    );
  return (
    <>
      <Link className="back" href="/discover">
        <ArrowLeft size={16} /> Back to discovery
      </Link>
      <section className="detail">
        <div className="detail-poster">
          <Poster url={movie.poster_url} title={movie.title} />
        </div>
        <div>
          <div className="eyebrow">THE BIGGER PICTURE · TMDB #{movie.id}</div>
          <h1>{movie.title}</h1>
          <p className="detail-meta">
            {movie.release_date || "Release date unavailable"} ·{" "}
            {movie.original_language?.toUpperCase() || "Language unavailable"}
          </p>
          <div className="genre-tags">
            {movie.genres.map((g) => (
              <span key={g.id}>{g.name}</span>
            ))}
          </div>
          <p className="overview">
            {movie.overview || "No overview is available for this movie."}
          </p>
          <div className="detail-stats">
            <div>
              Popularity<strong>{num(movie.popularity)}</strong>
            </div>
            <div>
              TMDB rating
              <strong>
                <Star size={18} />
                {num(movie.rating)} <small>/ 10</small>
              </strong>
            </div>
            <div>
              Votes<strong>{num(movie.vote_count, 0)}</strong>
            </div>
          </div>
          <p className="muted">
            Latest stored snapshot: {movie.snapshot_day} UTC
          </p>
          <a
            className="external"
            href={`https://www.themoviedb.org/movie/${movie.id}`}
            target="_blank"
            rel="noreferrer"
          >
            View on TMDB <ExternalLink size={14} />
          </a>
        </div>
      </section>
      <section className="history">
        <div className="eyebrow muted">FOLLOW THE MOMENTUM</div>
        <h2>The story so far</h2>
        <p>
          Actual daily observations. History begins with collection; gaps and
          missing scores are not filled.
        </p>
        {history.length < 2 ? (
          <div className="empty">
            <h3>One day is just the beginning.</h3>
            <p>
              {history.length === 1
                ? `First snapshot: ${history[0].day}. `
                : ""}
              A trend chart appears after a second UTC day is collected.
            </p>
          </div>
        ) : (
          <div className="charts">
            {(["popularity", "rating"] as const).map((metric) => (
              <div className="chart" key={metric}>
                <h3>
                  {metric === "rating"
                    ? "TMDB rating · out of 10"
                    : "TMDB popularity"}
                </h3>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart
                    data={history}
                    margin={{ top: 15, right: 15, bottom: 15, left: 0 }}
                  >
                    <CartesianGrid stroke="#303435" strokeDasharray="3 5" />
                    <XAxis
                      dataKey="day"
                      stroke="#a2aaa7"
                      tick={{ fontSize: 11 }}
                      minTickGap={40}
                    />
                    <YAxis
                      stroke="#a2aaa7"
                      domain={metric === "rating" ? [0, 10] : ["auto", "auto"]}
                      width={45}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "#202524",
                        border: "1px solid #414a46",
                        borderRadius: 10,
                      }}
                    />
                    <Line
                      dataKey={metric}
                      name={metric}
                      stroke="#b9e586"
                      strokeWidth={2}
                      connectNulls={false}
                      dot={{ r: 3 }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
                <details>
                  <summary>View observations as a table</summary>
                  <table>
                    <thead>
                      <tr>
                        <th>UTC date</th>
                        <th>{metric}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {history.map((p) => (
                        <tr key={p.day}>
                          <td>{p.day}</td>
                          <td>{num(p[metric], 3)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </details>
              </div>
            ))}
          </div>
        )}
      </section>
    </>
  );
}
