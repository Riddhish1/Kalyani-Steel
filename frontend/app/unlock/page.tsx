"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import logo from "../logo.png";

export default function UnlockPage() {
  const [pw, setPw] = useState("");
  const router = useRouter();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    // set cookie client-side; middleware will validate it on next request
    document.cookie = `ks_auth=${encodeURIComponent(pw)}; path=/; max-age=${60 * 60 * 24 * 30}`;
    router.push('/');
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 flex items-center justify-center p-6">
      <div className="w-full max-w-md">
        <div className="bg-white/95 backdrop-blur-sm border border-slate-200 rounded-2xl shadow-lg overflow-hidden">
          <div className="p-6 sm:p-8">
            <div className="flex items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-white flex items-center justify-center shadow-sm">
                <Image src={logo} alt="Kalyani Steel" width={48} height={48} />
              </div>
            </div>

            <h2 className="mt-4 text-center text-2xl font-semibold text-slate-800">Welcome back</h2>
            <p className="mt-2 text-center text-sm text-slate-500">Enter the site password to continue to the KSL Scrap Mix Optimizer</p>

            <form onSubmit={submit} className="mt-6">
              <label className="block text-sm font-medium text-slate-700 mb-2">Password</label>
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                className="block w-full rounded-lg border border-slate-200 px-4 py-2 shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="Enter password"
                aria-label="Password"
              />

              <button
                type="submit"
                className="mt-5 w-full inline-flex items-center justify-center rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 text-white px-4 py-2 text-sm font-medium shadow-md hover:scale-[1.01] transition"
              >
                Unlock
              </button>
            </form>

            <p className="mt-4 text-center text-xs text-slate-400">If you don’t have the password, contact the site administrator.</p>
          </div>
        </div>
      </div>
    </main>
  );
}
