"use client";

import { useState } from "react";
import { Sparkles, RefreshCw, Loader2 } from "lucide-react";
import { AISummary } from "@/lib/types";
import api from "@/lib/api";

interface AISummaryCardProps {
  summary: AISummary | null;
  contactId: string;
  loading: boolean;
  onRegenerated?: (summary: AISummary) => void;
}

export default function AISummaryCard({
  summary,
  contactId,
  loading,
  onRegenerated,
}: AISummaryCardProps) {
  const [regenerating, setRegenerating] = useState(false);

  const handleRegenerate = async () => {
    setRegenerating(true);
    try {
      const response = await api.post(`/contacts/${contactId}/ai-summary`);
      onRegenerated?.(response.data);
    } catch {
      // handle silently
    } finally {
      setRegenerating(false);
    }
  };

  if (loading) {
    return (
      <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-6 space-y-4">
        <div className="flex items-center gap-2">
          <div className="skeleton w-5 h-5 rounded" />
          <div className="skeleton h-5 w-32" />
        </div>
        <div className="skeleton h-4 w-full" />
        <div className="skeleton h-4 w-3/4" />
        <div className="skeleton h-4 w-1/2" />
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-bezalel-highlight" />
            <h3 className="text-sm font-semibold text-bezalel-text uppercase tracking-wider">
              AI Summary
            </h3>
          </div>
          <button
            onClick={handleRegenerate}
            disabled={regenerating}
            className="flex items-center gap-1.5 text-xs text-bezalel-highlight hover:text-bezalel-highlight/80 disabled:opacity-50"
          >
            {regenerating ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <RefreshCw className="w-3.5 h-3.5" />
            )}
            Generate
          </button>
        </div>
        <p className="text-sm text-bezalel-text-secondary">
          No AI summary available yet. Click Generate to create one.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-5 h-5 text-bezalel-highlight" />
          <h3 className="text-sm font-semibold text-bezalel-text uppercase tracking-wider">
            AI Summary
          </h3>
        </div>
        <button
          onClick={handleRegenerate}
          disabled={regenerating}
          className="flex items-center gap-1.5 text-xs text-bezalel-highlight hover:text-bezalel-highlight/80 disabled:opacity-50"
        >
          {regenerating ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <RefreshCw className="w-3.5 h-3.5" />
          )}
          Regenerate
        </button>
      </div>

      <div className="space-y-4">
        {/* Relationship Summary */}
        <div>
          <h4 className="text-xs text-bezalel-text-secondary uppercase tracking-wider mb-1">
            Relationship
          </h4>
          <p className="text-sm text-bezalel-text leading-relaxed">{summary.relationship_summary}</p>
        </div>

        {/* Key Topics */}
        {summary.key_topics.length > 0 && (
          <div>
            <h4 className="text-xs text-bezalel-text-secondary uppercase tracking-wider mb-2">
              Key Topics
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {summary.key_topics.map((topic, i) => (
                <span
                  key={i}
                  className="text-xs px-2.5 py-1 rounded-full bg-bezalel-highlight/10 text-bezalel-highlight border border-bezalel-highlight/20"
                >
                  {topic}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Last Interaction */}
        <div>
          <h4 className="text-xs text-bezalel-text-secondary uppercase tracking-wider mb-1">
            Last Interaction
          </h4>
          <p className="text-sm text-bezalel-text leading-relaxed">
            {summary.last_interaction_summary}
          </p>
        </div>

        {/* Suggested Next Action */}
        <div className="bg-bezalel-accent/50 border border-bezalel-border/50 rounded-lg p-3">
          <h4 className="text-xs text-bezalel-text-secondary uppercase tracking-wider mb-1">
            Suggested Next Action
          </h4>
          <p className="text-sm text-bezalel-highlight">{summary.suggested_next_action}</p>
        </div>
      </div>
    </div>
  );
}
