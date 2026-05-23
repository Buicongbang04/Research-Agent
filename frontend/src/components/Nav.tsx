"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { clearToken, isAuthed } from "@/lib/auth";

export default function Nav() {
  const [authed, setAuthed] = useState(false);
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    setAuthed(isAuthed());
  }, [pathname]);

  const logout = () => {
    clearToken();
    setAuthed(false);
    router.push("/login");
  };

  const link = (href: string, label: string) => {
    const active = pathname === href || pathname.startsWith(href + "/");
    return (
      <Link
        href={href}
        className={`px-3 py-1.5 rounded-md text-sm font-medium ${
          active ? "bg-slate-900 text-white" : "text-slate-700 hover:bg-slate-200"
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <nav className="border-b bg-white">
      <div className="mx-auto max-w-5xl px-4 py-3 flex items-center justify-between">
        <Link href="/research" className="font-bold text-lg">
          🔬 Research Agent
        </Link>
        <div className="flex items-center gap-1">
          {authed ? (
            <>
              {link("/research", "Research")}
              {link("/chat", "Chat")}
              <button
                onClick={logout}
                className="ml-2 px-3 py-1.5 text-sm text-slate-600 hover:text-red-600"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              {link("/login", "Login")}
              {link("/register", "Register")}
            </>
          )}
        </div>
      </div>
    </nav>
  );
}
