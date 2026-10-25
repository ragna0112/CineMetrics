"use client";
import { useState } from "react";
import { Film } from "lucide-react";
export default function Poster({
  url,
  title,
}: {
  url: string | null;
  title: string;
}) {
  const [failed, setFailed] = useState(false);
  return url && !failed ? (
    <img src={url} alt={`${title} poster`} onError={() => setFailed(true)} />
  ) : (
    <div className="poster-fallback">
      <Film size={38} />
      <span>Poster unavailable</span>
    </div>
  );
}
