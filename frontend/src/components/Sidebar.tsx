"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  Database,
  Pin,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";
import api from "@/lib/api";

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  badge?: string;
  disabled?: boolean;
}

const navItems: NavItem[] = [
  {
    label: "Rolodex.AI",
    href: "/apps/rolodex",
    icon: <Database className="w-5 h-5" />,
  },
  {
    label: "Placeholder 1",
    href: "/apps/placeholder",
    icon: <Pin className="w-5 h-5" />,
    badge: "Coming Soon",
    disabled: false,
  },
  {
    label: "Placeholder 2",
    href: "/apps/placeholder",
    icon: <Pin className="w-5 h-5" />,
    badge: "Coming Soon",
    disabled: false,
  },
  {
    label: "Placeholder 3",
    href: "/apps/placeholder",
    icon: <Pin className="w-5 h-5" />,
    badge: "Coming Soon",
    disabled: false,
  },
];

export default function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await api.post("/auth/logout");
    } catch {
      // proceed with logout regardless
    }
    router.push("/login");
  };

  const isActive = (href: string) => pathname.startsWith(href);

  return (
    <aside
      className={`h-screen bg-bezalel-secondary border-r border-bezalel-border flex flex-col transition-all duration-300 ${
        collapsed ? "w-16" : "w-64"
      }`}
    >
      {/* Wordmark */}
      <div className="flex items-center justify-between p-4 border-b border-bezalel-border min-h-[64px]">
        {!collapsed && (
          <h1 className="text-lg font-extralight tracking-[0.15em] text-bezalel-text whitespace-nowrap">
            Bezalel<span className="text-bezalel-highlight font-light">.AI</span>
          </h1>
        )}
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="p-1.5 rounded-md hover:bg-bezalel-accent text-bezalel-text-secondary hover:text-bezalel-text"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <button
            key={item.label}
            onClick={() => router.push(item.href)}
            disabled={item.disabled}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
              isActive(item.href)
                ? "bg-bezalel-highlight/10 text-bezalel-highlight border border-bezalel-highlight/20"
                : "text-bezalel-text-secondary hover:bg-bezalel-accent hover:text-bezalel-text border border-transparent"
            } ${item.disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"}`}
            title={collapsed ? item.label : undefined}
          >
            <span className="flex-shrink-0">{item.icon}</span>
            {!collapsed && (
              <>
                <span className="flex-1 text-left truncate">{item.label}</span>
                {item.badge && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-bezalel-accent text-bezalel-text-secondary border border-bezalel-border">
                    {item.badge}
                  </span>
                )}
              </>
            )}
          </button>
        ))}
      </nav>

      {/* Logout */}
      <div className="p-2 border-t border-bezalel-border">
        <button
          onClick={handleLogout}
          disabled={loggingOut}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-bezalel-text-secondary hover:bg-red-500/10 hover:text-red-400 transition-colors disabled:opacity-50"
          title={collapsed ? "Logout" : undefined}
        >
          {loggingOut ? (
            <Loader2 className="w-5 h-5 animate-spin flex-shrink-0" />
          ) : (
            <LogOut className="w-5 h-5 flex-shrink-0" />
          )}
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  );
}
