"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { Search, Upload, ChevronLeft, ChevronRight, Filter } from "lucide-react";
import ContactTable from "@/components/ContactTable";
import api from "@/lib/api";
import { Contact } from "@/lib/types";

const SOURCES = ["all", "gmail", "outlook", "imessage", "linkedin", "calendar"] as const;
const PAGE_SIZE = 25;

export default function RolodexPage() {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [companyFilter, setCompanyFilter] = useState<string>("");
  const [companies, setCompanies] = useState<string[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const fetchContacts = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        page,
        page_size: PAGE_SIZE,
      };
      if (search) params.search = search;
      if (sourceFilter !== "all") params.source = sourceFilter;
      if (companyFilter) params.company = companyFilter;

      const response = await api.get("/contacts", { params });
      setContacts(response.data.items || response.data);
      setTotalPages(response.data.total_pages || 1);

      // Extract unique companies for filter
      if (companies.length === 0 && response.data.companies) {
        setCompanies(response.data.companies);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [page, search, sourceFilter, companyFilter, companies.length]);

  useEffect(() => {
    fetchContacts();
  }, [fetchContacts]);

  useEffect(() => {
    setPage(1);
  }, [search, sourceFilter, companyFilter]);

  const handleImportCsv = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await api.post("/contacts/import/linkedin", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      fetchContacts();
    } catch {
      // handle error
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-light text-bezalel-text tracking-wide">
            Rolodex<span className="text-bezalel-highlight">.AI</span>
          </h1>
          <p className="text-sm text-bezalel-text-secondary mt-1">Contact Intelligence</p>
        </div>

        <div>
          <input
            ref={fileRef}
            type="file"
            accept=".csv"
            onChange={handleImportCsv}
            className="hidden"
          />
          <button
            onClick={() => fileRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-2 px-4 py-2 bg-bezalel-accent border border-bezalel-border rounded-lg text-sm text-bezalel-text hover:border-bezalel-highlight/50 transition-colors disabled:opacity-50"
          >
            <Upload className="w-4 h-4" />
            {uploading ? "Importing..." : "Import LinkedIn CSV"}
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-3 mb-6">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-bezalel-text-secondary" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search contacts..."
            className="w-full bg-bezalel-secondary border border-bezalel-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-bezalel-text placeholder-bezalel-text-secondary/50 focus:border-bezalel-highlight"
          />
        </div>

        <div className="flex gap-3">
          <div className="relative">
            <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-bezalel-text-secondary pointer-events-none" />
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="appearance-none bg-bezalel-secondary border border-bezalel-border rounded-lg pl-9 pr-8 py-2.5 text-sm text-bezalel-text cursor-pointer focus:border-bezalel-highlight"
            >
              {SOURCES.map((src) => (
                <option key={src} value={src}>
                  {src === "all" ? "All Sources" : src.charAt(0).toUpperCase() + src.slice(1)}
                </option>
              ))}
            </select>
          </div>

          <input
            type="text"
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
            placeholder="Filter by company..."
            className="bg-bezalel-secondary border border-bezalel-border rounded-lg px-4 py-2.5 text-sm text-bezalel-text placeholder-bezalel-text-secondary/50 focus:border-bezalel-highlight w-48"
          />
        </div>
      </div>

      {/* Table */}
      <ContactTable contacts={contacts} loading={loading} />

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-sm text-bezalel-text-secondary">
            Page {page} of {totalPages}
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-2 bg-bezalel-secondary border border-bezalel-border rounded-lg text-bezalel-text-secondary hover:text-bezalel-text hover:border-bezalel-highlight/50 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-2 bg-bezalel-secondary border border-bezalel-border rounded-lg text-bezalel-text-secondary hover:text-bezalel-text hover:border-bezalel-highlight/50 disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
