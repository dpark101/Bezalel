export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
  last_login: string;
}

export interface Contact {
  id: string;
  name: string;
  first_name: string;
  last_name: string;
  email: string;
  emails: string[];
  phone: string;
  phones: string[];
  company: string;
  title: string;
  linkedin_url: string;
  source: "gmail" | "outlook" | "imessage" | "linkedin" | "calendar" | "manual";
  sources: string[];
  last_contact_date: string;
  created_at: string;
  updated_at: string;
}

export interface Meeting {
  id: string;
  contact_id: string;
  title: string;
  date: string;
  type: "in_person" | "video" | "phone" | "email" | "message";
  summary: string;
  notes: string;
  source: string;
  created_at: string;
}

export interface ContactNote {
  id: string;
  contact_id: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface NewsItem {
  id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  summary?: string;
}

export interface NewsFeed {
  source: string;
  items: NewsItem[];
  last_updated: string;
}

export interface AISummary {
  contact_id: string;
  relationship_summary: string;
  key_topics: string[];
  last_interaction_summary: string;
  suggested_next_action: string;
  generated_at: string;
}

export interface LoginResponse {
  message: string;
  requires_otp: boolean;
  otp_expires_in: number;
}

export interface OTPVerifyResponse {
  message: string;
  user: User;
}
