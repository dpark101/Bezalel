"use client";

import { useState, useEffect, useCallback } from "react";
import Clock from "@/components/Clock";
import NewsFeed from "@/components/NewsFeed";
import api from "@/lib/api";
import { NewsFeed as NewsFeedType } from "@/lib/types";

const NEWS_SOURCES = [
  { key: "wsj", label: "Wall Street Journal" },
  { key: "nyt", label: "New York Times" },
  { key: "wapo", label: "Washington Post" },
];

export default function DashboardPage() {
  const [feeds, setFeeds] = useState<Record<string, NewsFeedType>>({});
  const [loading, setLoading] = useState(true);

  const fetchNews = useCallback(async () => {
    try {
      const response = await api.get("/news/feeds");
      const feedData: Record<string, NewsFeedType> = {};
      if (Array.isArray(response.data)) {
        response.data.forEach((feed: NewsFeedType) => {
          feedData[feed.source] = feed;
        });
      }
      setFeeds(feedData);
    } catch {
      // silently fail, keep existing data
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNews();
    const interval = setInterval(fetchNews, 5 * 60 * 1000); // 5 minutes
    return () => clearInterval(interval);
  }, [fetchNews]);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <Clock />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-6">
        {NEWS_SOURCES.map(({ key, label }) => (
          <NewsFeed
            key={key}
            source={label}
            items={feeds[key]?.items || []}
            loading={loading}
          />
        ))}
      </div>
    </div>
  );
}
