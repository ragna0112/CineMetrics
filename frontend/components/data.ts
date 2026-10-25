export type Movie = {
  id: number;
  title: string;
  overview: string | null;
  poster_url: string | null;
  release_date: string | null;
  original_language: string | null;
  genres: { id: number; name: string }[];
  popularity: number | null;
  rating: number | null;
  vote_count: number | null;
  snapshot_day: string;
  change?: number;
  percent_change?: number | null;
};
export type Summary = {
  movies: number;
  average_rating: number | null;
  average_popularity: number | null;
  total_votes: number | null;
  first_day: string | null;
  latest_day: string | null;
  last_refresh: string | null;
};
export const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
export async function request<T>(
  path: string,
  signal?: AbortSignal,
): Promise<T> {
  const r = await fetch(`${api}${path}`, { signal, cache: "no-store" });
  if (!r.ok)
    throw Error(
      r.status === 404
        ? "This movie has not been collected."
        : "The data service is unavailable. Check that the backend and database are running.",
    );
  return r.json();
}
export function num(v: number | null | undefined, d = 1) {
  return v == null
    ? "—"
    : v.toLocaleString(undefined, { maximumFractionDigits: d });
}
