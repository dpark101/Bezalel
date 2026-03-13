"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { formatDistanceToNow } from "date-fns";
import {
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  Mail,
  MessageSquare,
  Linkedin,
  Calendar,
  Monitor,
} from "lucide-react";
import { Contact } from "@/lib/types";

interface ContactTableProps {
  contacts: Contact[];
  loading: boolean;
}

type SortField = "name" | "company" | "title" | "last_contact_date";
type SortDirection = "asc" | "desc";

const sourceIcons: Record<string, React.ReactNode> = {
  gmail: <span title="Gmail"><Mail className="w-3.5 h-3.5 text-red-400" /></span>,
  outlook: <span title="Outlook"><Mail className="w-3.5 h-3.5 text-blue-400" /></span>,
  imessage: <span title="iMessage"><MessageSquare className="w-3.5 h-3.5 text-green-400" /></span>,
  linkedin: <span title="LinkedIn"><Linkedin className="w-3.5 h-3.5 text-sky-400" /></span>,
  calendar: <span title="Calendar"><Calendar className="w-3.5 h-3.5 text-yellow-400" /></span>,
  manual: <span title="Manual"><Monitor className="w-3.5 h-3.5 text-bezalel-text-secondary" /></span>,
};

function SkeletonRow() {
  return (
    <tr className="border-b border-bezalel-border/30">
      {[...Array(5)].map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="skeleton h-4 w-3/4" />
        </td>
      ))}
    </tr>
  );
}

export default function ContactTable({ contacts, loading }: ContactTableProps) {
  const router = useRouter();
  const [sortField, setSortField] = useState<SortField>("last_contact_date");
  const [sortDir, setSortDir] = useState<SortDirection>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDir("asc");
    }
  };

  const sorted = [...contacts].sort((a, b) => {
    let cmp = 0;
    const valA = a[sortField] || "";
    const valB = b[sortField] || "";
    cmp = valA < valB ? -1 : valA > valB ? 1 : 0;
    return sortDir === "asc" ? cmp : -cmp;
  });

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return <ArrowUpDown className="w-3 h-3 opacity-30" />;
    return sortDir === "asc" ? (
      <ArrowUp className="w-3 h-3 text-bezalel-highlight" />
    ) : (
      <ArrowDown className="w-3 h-3 text-bezalel-highlight" />
    );
  };

  const columns: { label: string; field: SortField }[] = [
    { label: "Name", field: "name" },
    { label: "Company", field: "company" },
    { label: "Title", field: "title" },
    { label: "Last Contact", field: "last_contact_date" },
  ];

  return (
    <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-bezalel-border bg-bezalel-accent/30">
              {columns.map((col) => (
                <th
                  key={col.field}
                  className="text-left px-4 py-3 text-xs font-semibold text-bezalel-text-secondary uppercase tracking-wider cursor-pointer hover:text-bezalel-text select-none"
                  onClick={() => handleSort(col.field)}
                >
                  <div className="flex items-center gap-1.5">
                    {col.label}
                    <SortIcon field={col.field} />
                  </div>
                </th>
              ))}
              <th className="text-left px-4 py-3 text-xs font-semibold text-bezalel-text-secondary uppercase tracking-wider">
                Sources
              </th>
            </tr>
          </thead>
          <tbody>
            {loading
              ? Array.from({ length: 8 }).map((_, i) => <SkeletonRow key={i} />)
              : sorted.map((contact) => (
                  <tr
                    key={contact.id}
                    onClick={() => router.push(`/apps/rolodex/${contact.id}`)}
                    className="border-b border-bezalel-border/30 hover:bg-bezalel-accent/40 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-bezalel-text font-medium">
                      {contact.name}
                    </td>
                    <td className="px-4 py-3 text-bezalel-text-secondary">
                      {contact.company || "---"}
                    </td>
                    <td className="px-4 py-3 text-bezalel-text-secondary">
                      {contact.title || "---"}
                    </td>
                    <td className="px-4 py-3 text-bezalel-text-secondary">
                      {contact.last_contact_date
                        ? formatDistanceToNow(new Date(contact.last_contact_date), {
                            addSuffix: true,
                          })
                        : "---"}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5">
                        {(contact.sources || [contact.source]).map((src, i) => (
                          <span key={i}>{sourceIcons[src] || null}</span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
            {!loading && sorted.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-12 text-center text-bezalel-text-secondary">
                  No contacts found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
