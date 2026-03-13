"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { format, formatDistanceToNow } from "date-fns";
import {
  ArrowLeft,
  Mail,
  Phone,
  Linkedin,
  Building2,
  Briefcase,
  CalendarDays,
  Plus,
  Save,
  X,
  Pencil,
  Loader2,
} from "lucide-react";
import api from "@/lib/api";
import { Contact, Meeting, ContactNote, AISummary } from "@/lib/types";
import ContactTimeline from "@/components/ContactTimeline";
import AISummaryCard from "@/components/AISummaryCard";

const typeBadgeColors: Record<string, string> = {
  in_person: "bg-green-400/10 text-green-400",
  video: "bg-blue-400/10 text-blue-400",
  phone: "bg-yellow-400/10 text-yellow-400",
  email: "bg-red-400/10 text-red-400",
  message: "bg-purple-400/10 text-purple-400",
};

export default function ContactDetailPage() {
  const params = useParams();
  const router = useRouter();
  const contactId = params.id as string;

  const [contact, setContact] = useState<Contact | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [notes, setNotes] = useState<ContactNote[]>([]);
  const [aiSummary, setAiSummary] = useState<AISummary | null>(null);
  const [lastMeeting, setLastMeeting] = useState<Meeting | null>(null);

  const [loadingContact, setLoadingContact] = useState(true);
  const [loadingMeetings, setLoadingMeetings] = useState(true);
  const [loadingNotes, setLoadingNotes] = useState(true);
  const [loadingSummary, setLoadingSummary] = useState(true);

  const [newNote, setNewNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null);
  const [editingNoteContent, setEditingNoteContent] = useState("");

  const fetchContact = useCallback(async () => {
    try {
      const response = await api.get(`/contacts/${contactId}`);
      setContact(response.data);
    } catch {
      // handle error
    } finally {
      setLoadingContact(false);
    }
  }, [contactId]);

  const fetchMeetings = useCallback(async () => {
    try {
      const response = await api.get(`/contacts/${contactId}/meetings`);
      const data = response.data;
      setMeetings(data);
      if (data.length > 0) {
        setLastMeeting(data[0]);
      }
    } catch {
      // handle error
    } finally {
      setLoadingMeetings(false);
    }
  }, [contactId]);

  const fetchNotes = useCallback(async () => {
    try {
      const response = await api.get(`/contacts/${contactId}/notes`);
      setNotes(response.data);
    } catch {
      // handle error
    } finally {
      setLoadingNotes(false);
    }
  }, [contactId]);

  const fetchSummary = useCallback(async () => {
    try {
      const response = await api.get(`/contacts/${contactId}/ai-summary`);
      setAiSummary(response.data);
    } catch {
      // 404 is expected if no summary exists
    } finally {
      setLoadingSummary(false);
    }
  }, [contactId]);

  useEffect(() => {
    fetchContact();
    fetchMeetings();
    fetchNotes();
    fetchSummary();
  }, [fetchContact, fetchMeetings, fetchNotes, fetchSummary]);

  const handleSaveNote = async () => {
    if (!newNote.trim()) return;
    setSavingNote(true);
    try {
      await api.post(`/contacts/${contactId}/notes`, { content: newNote });
      setNewNote("");
      fetchNotes();
    } catch {
      // handle error
    } finally {
      setSavingNote(false);
    }
  };

  const handleUpdateNote = async (noteId: string) => {
    if (!editingNoteContent.trim()) return;
    try {
      await api.put(`/contacts/${contactId}/notes/${noteId}`, {
        content: editingNoteContent,
      });
      setEditingNoteId(null);
      setEditingNoteContent("");
      fetchNotes();
    } catch {
      // handle error
    }
  };

  if (loadingContact) {
    return (
      <div className="p-8 max-w-5xl mx-auto">
        <div className="space-y-6">
          <div className="skeleton h-8 w-48" />
          <div className="skeleton h-4 w-72" />
          <div className="skeleton h-64 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  if (!contact) {
    return (
      <div className="p-8 max-w-5xl mx-auto text-center py-20">
        <p className="text-bezalel-text-secondary">Contact not found</p>
        <button
          onClick={() => router.push("/apps/rolodex")}
          className="mt-4 text-bezalel-highlight hover:underline text-sm"
        >
          Back to contacts
        </button>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      {/* Back button */}
      <button
        onClick={() => router.push("/apps/rolodex")}
        className="flex items-center gap-1.5 text-sm text-bezalel-text-secondary hover:text-bezalel-text mb-6 group"
      >
        <ArrowLeft className="w-4 h-4 group-hover:-translate-x-1 transition-transform" />
        Back to contacts
      </button>

      {/* Header */}
      <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-6 mb-6">
        <h1 className="text-2xl font-light text-bezalel-text mb-1">{contact.name}</h1>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-3 text-sm text-bezalel-text-secondary">
          {contact.title && (
            <div className="flex items-center gap-1.5">
              <Briefcase className="w-3.5 h-3.5" />
              {contact.title}
            </div>
          )}
          {contact.company && (
            <div className="flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5" />
              {contact.company}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 mt-3 text-sm">
          {(contact.emails || [contact.email]).filter(Boolean).map((email, i) => (
            <a
              key={i}
              href={`mailto:${email}`}
              className="flex items-center gap-1.5 text-bezalel-text-secondary hover:text-bezalel-highlight"
            >
              <Mail className="w-3.5 h-3.5" />
              {email}
            </a>
          ))}
          {(contact.phones || [contact.phone]).filter(Boolean).map((phone, i) => (
            <a
              key={i}
              href={`tel:${phone}`}
              className="flex items-center gap-1.5 text-bezalel-text-secondary hover:text-bezalel-highlight"
            >
              <Phone className="w-3.5 h-3.5" />
              {phone}
            </a>
          ))}
          {contact.linkedin_url && (
            <a
              href={contact.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-bezalel-text-secondary hover:text-bezalel-highlight"
            >
              <Linkedin className="w-3.5 h-3.5" />
              LinkedIn
            </a>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Last Met card */}
        <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <CalendarDays className="w-5 h-5 text-bezalel-highlight" />
            <h3 className="text-sm font-semibold text-bezalel-text uppercase tracking-wider">
              Last Met
            </h3>
          </div>

          {loadingMeetings ? (
            <div className="space-y-2">
              <div className="skeleton h-4 w-32" />
              <div className="skeleton h-4 w-48" />
            </div>
          ) : lastMeeting ? (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="text-bezalel-text">
                  {format(new Date(lastMeeting.date), "MMMM d, yyyy")}
                </span>
                <span className="text-xs text-bezalel-text-secondary">
                  ({formatDistanceToNow(new Date(lastMeeting.date), { addSuffix: true })})
                </span>
              </div>
              <span
                className={`inline-block text-xs px-2 py-0.5 rounded-full mb-2 ${
                  typeBadgeColors[lastMeeting.type] || "bg-bezalel-accent text-bezalel-text-secondary"
                }`}
              >
                {lastMeeting.type.replace("_", " ")}
              </span>
              {lastMeeting.summary && (
                <p className="text-sm text-bezalel-text-secondary mt-1">{lastMeeting.summary}</p>
              )}
            </div>
          ) : (
            <p className="text-sm text-bezalel-text-secondary">No meetings recorded</p>
          )}
        </div>

        {/* AI Summary */}
        <AISummaryCard
          summary={aiSummary}
          contactId={contactId}
          loading={loadingSummary}
          onRegenerated={(s) => setAiSummary(s)}
        />
      </div>

      {/* Interaction Timeline */}
      <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-6 mb-6">
        <h3 className="text-sm font-semibold text-bezalel-text uppercase tracking-wider mb-6">
          Interaction Timeline
        </h3>
        <ContactTimeline meetings={meetings} loading={loadingMeetings} />
      </div>

      {/* Notes */}
      <div className="bg-bezalel-secondary border border-bezalel-border rounded-xl p-6">
        <h3 className="text-sm font-semibold text-bezalel-text uppercase tracking-wider mb-4">
          Notes
        </h3>

        {/* Add new note */}
        <div className="mb-6">
          <textarea
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            placeholder="Add a note..."
            rows={3}
            className="w-full bg-bezalel-accent border border-bezalel-border rounded-lg px-4 py-3 text-sm text-bezalel-text placeholder-bezalel-text-secondary/50 focus:border-bezalel-highlight resize-none"
          />
          <div className="flex justify-end mt-2">
            <button
              onClick={handleSaveNote}
              disabled={!newNote.trim() || savingNote}
              className="flex items-center gap-1.5 px-4 py-2 bg-bezalel-highlight hover:bg-bezalel-highlight/90 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm rounded-lg"
            >
              {savingNote ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <Plus className="w-3.5 h-3.5" />
              )}
              Save Note
            </button>
          </div>
        </div>

        {/* Existing notes */}
        {loadingNotes ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="skeleton h-16 w-full rounded-lg" />
            ))}
          </div>
        ) : notes.length > 0 ? (
          <div className="space-y-3">
            {notes.map((note) => (
              <div
                key={note.id}
                className="bg-bezalel-accent/50 border border-bezalel-border/50 rounded-lg p-4"
              >
                {editingNoteId === note.id ? (
                  <div>
                    <textarea
                      value={editingNoteContent}
                      onChange={(e) => setEditingNoteContent(e.target.value)}
                      rows={3}
                      className="w-full bg-bezalel-accent border border-bezalel-border rounded-lg px-3 py-2 text-sm text-bezalel-text focus:border-bezalel-highlight resize-none"
                    />
                    <div className="flex justify-end gap-2 mt-2">
                      <button
                        onClick={() => setEditingNoteId(null)}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs text-bezalel-text-secondary hover:text-bezalel-text border border-bezalel-border rounded-lg"
                      >
                        <X className="w-3 h-3" />
                        Cancel
                      </button>
                      <button
                        onClick={() => handleUpdateNote(note.id)}
                        className="flex items-center gap-1 px-3 py-1.5 text-xs bg-bezalel-highlight text-white rounded-lg"
                      >
                        <Save className="w-3 h-3" />
                        Save
                      </button>
                    </div>
                  </div>
                ) : (
                  <div>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm text-bezalel-text whitespace-pre-wrap">{note.content}</p>
                      <button
                        onClick={() => {
                          setEditingNoteId(note.id);
                          setEditingNoteContent(note.content);
                        }}
                        className="p-1 text-bezalel-text-secondary hover:text-bezalel-text flex-shrink-0"
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                    </div>
                    <p className="text-xs text-bezalel-text-secondary mt-2">
                      {format(new Date(note.created_at), "MMM d, yyyy 'at' h:mm a")}
                      {note.updated_at !== note.created_at && " (edited)"}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-bezalel-text-secondary text-center py-4">
            No notes yet
          </p>
        )}
      </div>
    </div>
  );
}
