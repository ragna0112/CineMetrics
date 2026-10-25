import Link from "next/link";
import { Star, ArrowUpRight } from "lucide-react";
import { Movie, num } from "./data";
import Poster from "./Poster";
export default function Card({
  movie: m,
  rank,
}: {
  movie: Movie;
  rank: number;
}) {
  return (
    <Link href={`/movies/${m.id}`} className="movie-card">
      <div className="poster">
        <Poster url={m.poster_url} title={m.title} />
        <span className="rank">{String(rank).padStart(2, "0")}</span>
        <span className="open">
          <ArrowUpRight size={20} />
        </span>
        <span className="rating">
          <Star size={12} fill="currentColor" /> {num(m.rating)}
        </span>
      </div>
      <h3>{m.title}</h3>
      <div className="card-meta">
        <span>
          {m.release_date?.slice(0, 4) || "Unreleased"} <b>·</b>{" "}
          {m.genres[0]?.name || "Uncategorized"}
        </span>
      </div>
      <div className="card-bottom">
        <span>{m.change != null ? "Popularity gain" : "Popularity"}</span>
        <strong className={m.change != null ? "mint" : ""}>
          {m.change != null ? "+" : ""}
          {num(m.change ?? m.popularity)} <ArrowUpRight size={13} />
        </strong>
      </div>
    </Link>
  );
}
