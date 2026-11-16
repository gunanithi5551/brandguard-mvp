import React, { useState } from 'react';
import axios from 'axios';
import {
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Copy,
  FileText,
  BookOpen
} from 'lucide-react';

const SAMPLE_VIOLATION = "We guarantee a 100% ROI for our customers!";
const SAMPLE_COMPLIANT = "We partner closely with our Clients to support sustainable operational efficiency.";

export default function App() {
  const [draftContent, setDraftContent] = useState(SAMPLE_VIOLATION);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);

  const handleRunBrandCheck = async () => {
    if (!draftContent.trim()) return;
    setLoading(true);
    setError(null);
    setCopied(false);

    try {
      const response = await axios.post('http://localhost:8000/api/review', {
        content: draftContent,
      });
      setResult(response.data);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          'Unable to reach BrandGuard AI backend at http://localhost:8000/api/review. Ensure FastAPI is running.'
      );
    } finally {
      setLoading(false);
    }
  };

  const handleCopySuggestion = () => {
    if (!result?.suggestion) return;
    navigator.clipboard.writeText(result.suggestion);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleApplySuggestion = () => {
    if (!result?.suggestion) return;
    setDraftContent(result.suggestion);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      {/* Enterprise Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-indigo-500/10 border border-indigo-500/30 text-indigo-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-white">
                BrandGuard AI - Governance Portal
              </h1>
              <p className="text-xs text-slate-400">
                Multi-Agent CrewAI &amp; ChromaDB Real-Time Compliance Auditor
              </p>
            </div>
          </div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            ChromaDB Guidelines Active
          </span>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto w-full px-6 py-8 grid grid-cols-1 lg:grid-cols-12 gap-8 flex-1">
        {/* Left Column: Draft Input & Guidelines */}
        <section className="lg:col-span-7 flex flex-col gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <label
                htmlFor="draft-input"
                className="flex items-center gap-2 text-sm font-semibold text-slate-200"
              >
                <FileText className="w-4 h-4 text-indigo-400" />
                Draft Marketing / Corporate Copy
              </label>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setDraftContent(SAMPLE_VIOLATION)}
                  className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                >
                  Load Violation Sample
                </button>
                <button
                  type="button"
                  onClick={() => setDraftContent(SAMPLE_COMPLIANT)}
                  className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition"
                >
                  Load Compliant Sample
                </button>
              </div>
            </div>

            <textarea
              id="draft-input"
              rows={6}
              value={draftContent}
              onChange={(e) => setDraftContent(e.target.value)}
              placeholder="Paste your campaign copy, email draft, or press release here for brand compliance verification..."
              className="w-full rounded-xl bg-slate-950 border border-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 p-4 text-sm text-slate-100 placeholder-slate-500 outline-none transition resize-y"
            />

            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs text-slate-400">
                {draftContent.length} characters
              </span>
              <button
                type="button"
                onClick={handleRunBrandCheck}
                disabled={loading || !draftContent.trim()}
                className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold text-sm bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white shadow-lg shadow-indigo-600/25 transition"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Auditing with CrewAI...
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    Run Brand Check
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Active ChromaDB Guidelines Reference Card */}
          <div className="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-5">
            <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
              <BookOpen className="w-4 h-4 text-indigo-400" />
              Active ChromaDB Brand Guidelines
            </div>
            <ul className="space-y-2 text-xs text-slate-300">
              <li className="flex items-start gap-2">
                <span className="font-bold text-indigo-400">1.</span>
                Always use a professional tone.
              </li>
              <li className="flex items-start gap-2">
                <span className="font-bold text-indigo-400">2.</span>
                Never guarantee ROI or specific financial outcomes.
              </li>
              <li className="flex items-start gap-2">
                <span className="font-bold text-indigo-400">3.</span>
                Refer to users as &apos;Clients&apos;, never &apos;Customers&apos;.
              </li>
            </ul>
          </div>
        </section>

        {/* Right Column: Results Dashboard */}
        <section className="lg:col-span-5 flex flex-col gap-6">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl flex-1 flex flex-col">
            <h2 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-indigo-400" />
              Compliance Results Dashboard
            </h2>

            {error && (
              <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 text-xs text-red-300 mb-4">
                {error}
              </div>
            )}

            {!result && !loading && !error && (
              <div className="flex-1 flex flex-col items-center justify-center text-center py-12 text-slate-500">
                <ShieldCheck className="w-12 h-12 mb-3 text-slate-700" />
                <p className="text-sm font-medium text-slate-400">
                  Ready for Compliance Audit
                </p>
                <p className="text-xs mt-1 max-w-xs">
                  Click &ldquo;Run Brand Check&rdquo; to inspect your draft against ChromaDB governance rules.
                </p>
              </div>
            )}

            {loading && (
              <div className="flex-1 flex flex-col items-center justify-center text-center py-12">
                <Loader2 className="w-10 h-10 text-indigo-400 animate-spin mb-3" />
                <p className="text-sm font-medium text-slate-200">
                  Running Multi-Agent Brand Audit...
                </p>
                <p className="text-xs text-slate-400 mt-1">
                  Compliance Auditor &amp; Correction Editor are inspecting your draft
                </p>
              </div>
            )}

            {result && !loading && (
              <div className="space-y-4">
                {/* Status Banner */}
                <div className="flex items-center justify-between px-4 py-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-xs font-medium text-slate-400">Audit Status</span>
                  {result.status === 'flagged' ? (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Flagged Violation
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      Approved
                    </span>
                  )}
                </div>

                {/* Red/Yellow Warning Box for Flagged Status */}
                {result.status === 'flagged' && (
                  <div className="rounded-xl bg-red-950/40 border border-amber-500/40 p-4 space-y-3">
                    <div>
                      <div className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                        Broken Rule
                      </div>
                      <p className="mt-1 text-sm font-semibold text-red-200">
                        {result.broken_rule}
                      </p>
                    </div>
                    <div className="border-t border-red-500/20 pt-2.5">
                      <div className="text-xs font-semibold uppercase tracking-wider text-amber-300/90">
                        Auditor Explanation
                      </div>
                      <p className="mt-1 text-xs leading-relaxed text-slate-200">
                        {result.explanation}
                      </p>
                    </div>
                  </div>
                )}

                {result.status !== 'flagged' && (
                  <div className="rounded-xl bg-emerald-950/30 border border-emerald-500/30 p-4">
                    <div className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                      Audit Explanation
                    </div>
                    <p className="mt-1 text-xs leading-relaxed text-slate-200">
                      {result.explanation}
                    </p>
                  </div>
                )}

                {/* Green Box for Compliant Suggestion */}
                <div className="rounded-xl bg-emerald-950/40 border border-emerald-500/40 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      Correction Editor Suggestion
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleCopySuggestion}
                        className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 transition"
                      >
                        <Copy className="w-3 h-3" />
                        {copied ? 'Copied' : 'Copy'}
                      </button>
                      <button
                        type="button"
                        onClick={handleApplySuggestion}
                        className="text-xs px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-medium transition"
                      >
                        Replace Draft
                      </button>
                    </div>
                  </div>
                  <p className="text-sm font-medium text-emerald-100 bg-slate-950/60 p-3 rounded-lg border border-emerald-500/20">
                    {result.suggestion}
                  </p>
                </div>
              </div>
            )}
          </div>
        </section>
      </main>
    </div>
  );
}
