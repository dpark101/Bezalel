"use client";

import { Lock } from "lucide-react";

export default function PlaceholderPage() {
  return (
    <div className="flex items-center justify-center h-full min-h-[60vh]">
      <div className="text-center animate-fade-in">
        <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-bezalel-accent border border-bezalel-border mb-6">
          <Lock className="w-7 h-7 text-bezalel-text-secondary" />
        </div>
        <h2 className="text-xl font-light text-bezalel-text mb-2">Coming Soon</h2>
        <p className="text-sm text-bezalel-text-secondary max-w-xs mx-auto">
          This module is currently under development. Check back soon for updates.
        </p>
      </div>
    </div>
  );
}
