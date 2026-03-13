"use client";

import { formatDistanceToNow } from "date-fns";
import { ExternalLink } from "lucide-react";
import { NewsItem } from "@/lib/types";

interface NewsFeedProps {
  source: string;
  items: NewsItem[];
  loading: boolean;
}

function SkeletonLine({ width }: { width: string }) {
  return <div className={`skeleton h-4 ${width}`} />;
}

export default function NewsFeed({ source, items, loading }: NewsFeedProps) {
  return (
    <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-5 py-4 border-b border-bezalel-border">
        <h3 className="text-sm font-semibold text-bezalel-text uppercase tracking-wider">
          {source}
        </h3>
      </div>

      {/* Headlines */}
      <div className="divide-y divide-bezalel-border/50">
        {loading
          ? Array.from({ length: 10 }).map((_, i) => (
              <div key={i} className="px-5 py-3.5 space-y-2">
                <SkeletonLine width="w-full" />
                <SkeletonLine width="w-1/4" />
              </div>
            ))
          : items.map((item) => (
              <a
                key={item.id}
                href={item.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block px-5 py-3.5 hover:bg-bezalel-accent/50 transition-colors group"
              >
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-sm text-bezalel-text leading-snug group-hover:text-bezalel-highlight transition-colors">
                    {item.title}
                  </h4>
                  <ExternalLink className="w-3 h-3 text-bezalel-text-secondary/50 group-hover:text-bezalel-highlight flex-shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity" />
                </div>
                <p className="text-xs text-bezalel-text-secondary mt-1">
                  {formatDistanceToNow(new Date(item.published_at), { addSuffix: true })}
                </p>
              </a>
            ))}

        {!loading && items.length === 0 && (
          <div className="px-5 py-8 text-center text-sm text-bezalel-text-secondary">
            No headlines available
          </div>
        )}
      </div>
    </div>
  );
}
