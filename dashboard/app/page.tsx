"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Prospect } from "@/lib/types";
import { Card } from "./ui";

export default function ProspectsPage() {
  const [prospects, setProspects] = useState<Prospect[] | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    api
      .listProspects()
      .then(setProspects)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return (
      <Card>
        <p className="text-sm text-red-600">Couldn&apos;t load prospects: {error}</p>
        <p className="mt-2 text-xs text-neutral-500">
          Is the backend running at{" "}
          <code>{process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1"}</code>?
        </p>
      </Card>
    );
  }

  if (!prospects) {
    return <p className="text-sm text-neutral-500">Loading…</p>;
  }

  if (prospects.length === 0) {
    return (
      <Card>
        <p className="text-sm">No prospects yet.</p>
        <p className="mt-1 text-xs text-neutral-500">
          Capture one from the Chrome extension while viewing a LinkedIn profile.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-2">
      <h1 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
        Prospects
      </h1>
      {prospects.map((p) => (
        <Link key={p.id} href={`/prospects/${p.id}`} className="block">
          <Card className="transition hover:border-neutral-400 dark:hover:border-neutral-600">
            <div className="flex items-baseline justify-between">
              <span className="font-medium">{p.full_name}</span>
              <span className="text-xs text-neutral-500">
                {new Date(p.captured_at).toLocaleDateString()}
              </span>
            </div>
            {p.headline && (
              <div className="text-sm text-neutral-600 dark:text-neutral-400">
                {p.headline}
              </div>
            )}
            {p.company && (
              <div className="mt-1 text-xs text-neutral-500">{p.company.name}</div>
            )}
          </Card>
        </Link>
      ))}
    </div>
  );
}
