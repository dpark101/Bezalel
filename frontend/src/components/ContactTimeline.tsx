"use client";

import { useState } from "react";
import { format } from "date-fns";
import {
  Video,
  Phone,
  Mail,
  MessageSquare,
  Users,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Meeting } from "@/lib/types";

interface ContactTimelineProps {
  meetings: Meeting[];
  loading: boolean;
}

const typeConfig: Record<string, { icon: React.ReactNode; label: string; color: string }> = {
  in_person: { icon: <Users className="w-4 h-4" />, label: "In Person", color: "text-green-400 bg-green-400/10" },
  video: { icon: <Video className="w-4 h-4" />, label: "Video Call", color: "text-blue-400 bg-blue-400/10" },
  phone: { icon: <Phone className="w-4 h-4" />, label: "Phone Call", color: "text-yellow-400 bg-yellow-400/10" },
  email: { icon: <Mail className="w-4 h-4" />, label: "Email", color: "text-red-400 bg-red-400/10" },
  message: { icon: <MessageSquare className="w-4 h-4" />, label: "Message", color: "text-purple-400 bg-purple-400/10" },
};

function TimelineItem({ meeting }: { meeting: Meeting }) {
  const [expanded, setExpanded] = useState(false);
  const config = typeConfig[meeting.type] || typeConfig.email;

  return (
    <div className="relative pl-8 pb-6 last:pb-0">
      {/* Timeline line */}
      <div className="absolute left-[11px] top-6 bottom-0 w-px bg-bezalel-border" />

      {/* Timeline dot */}
      <div className={`absolute left-0 top-1 w-6 h-6 rounded-full flex items-center justify-center ${config.color}`}>
        {config.icon}
      </div>

      {/* Card */}
      <div className="bg-bezalel-accent/50 border border-bezalel-border/50 rounded-lg p-4 hover:border-bezalel-border transition-colors">
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className={`text-xs px-2 py-0.5 rounded-full ${config.color}`}>
                {config.label}
              </span>
              <span className="text-xs text-bezalel-text-secondary">
                {format(new Date(meeting.date), "MMM d, yyyy 'at' h:mm a")}
              </span>
            </div>
            <h4 className="text-sm font-medium text-bezalel-text">{meeting.title}</h4>
            {meeting.summary && (
              <p className="text-sm text-bezalel-text-secondary mt-1 line-clamp-2">
                {meeting.summary}
              </p>
            )}
          </div>

          {meeting.notes && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="p-1 text-bezalel-text-secondary hover:text-bezalel-text flex-shrink-0"
            >
              {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
        </div>

        {expanded && meeting.notes && (
          <div className="mt-3 pt-3 border-t border-bezalel-border/50 text-sm text-bezalel-text-secondary whitespace-pre-wrap">
            {meeting.notes}
          </div>
        )}
      </div>
    </div>
  );
}

export default function ContactTimeline({ meetings, loading }: ContactTimelineProps) {
  if (loading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="pl-8 relative">
            <div className="absolute left-0 top-1 w-6 h-6 rounded-full skeleton" />
            <div className="bg-bezalel-accent/50 border border-bezalel-border/50 rounded-lg p-4 space-y-2">
              <div className="skeleton h-3 w-24" />
              <div className="skeleton h-4 w-3/4" />
              <div className="skeleton h-3 w-1/2" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (meetings.length === 0) {
    return (
      <div className="text-center py-12 text-bezalel-text-secondary text-sm">
        No interactions recorded
      </div>
    );
  }

  return (
    <div>
      {meetings.map((meeting) => (
        <TimelineItem key={meeting.id} meeting={meeting} />
      ))}
    </div>
  );
}
