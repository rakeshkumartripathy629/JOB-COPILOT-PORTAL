import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  Check,
  Copy,
  FileText,
  Pencil,
  Plus,
  Save,
  Trash2,
  X,
} from "lucide-react";
import api from "../services/api";
import { getApiError } from "../utils/apiError";
import { CoverLetter, Job, Resume } from "../types";
import { Button } from "../components/ui/button";

export default function CoverLetterPage() {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<number | "">("");
  const [resumeId, setResumeId] = useState<number | "">("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [copied, setCopied] = useState<number | null>(null);
  const [editId, setEditId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");

  const { data: letters } = useQuery({
    queryKey: ["cover-letters"],
    queryFn: async () =>
      (await api.get("/cover-letters")).data as CoverLetter[],
  });

  const { data: allJobs } = useQuery({
    queryKey: ["all-jobs"],
    queryFn: async () =>
      (await api.get("/jobs/search?limit=50")).data as Job[],
  });

  const { data: resumes } = useQuery({
    queryKey: ["resumes"],
    queryFn: async () => (await api.get("/resumes")).data as Resume[],
  });

  const create = useMutation({
    mutationFn: async () => {
      const { data } = await api.post<CoverLetter>("/cover-letters", {
        job_id: Number(jobId),
        resume_id: resumeId === "" ? null : Number(resumeId),
      });
      return data;
    },
    onSuccess: (letter) => {
      toast.success("Cover letter generated");
      setExpanded(letter.id);
      qc.invalidateQueries({ queryKey: ["cover-letters"] });
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const remove = useMutation({
    mutationFn: async (id: number) => api.delete(`/cover-letters/${id}`),
    onSuccess: () => {
      toast.success("Deleted");
      qc.invalidateQueries({ queryKey: ["cover-letters"] });
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  const saveEdit = useMutation({
    mutationFn: async ({ id, content }: { id: number; content: string }) =>
      (await api.patch<CoverLetter>(`/cover-letters/${id}`, { content })).data,
    onSuccess: () => {
      toast.success("Cover letter updated");
      setEditId(null);
      qc.invalidateQueries({ queryKey: ["cover-letters"] });
    },
    onError: (err) => toast.error(getApiError(err)),
  })

  async function copyContent(letter: CoverLetter) {
    await navigator.clipboard.writeText(letter.content);
    setCopied(letter.id);
    setTimeout(() => setCopied(null), 1500);
  }

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold">Cover Letters</h1>

      <div className="p-4 border rounded-lg space-y-4 max-w-xl">
        <label className="block">
          <span className="text-sm font-medium">Job</span>
          <select
            value={jobId}
            onChange={(e) =>
              setJobId(e.target.value ? Number(e.target.value) : "")
            }
            className="w-full mt-1 p-2 border rounded bg-background"
          >
            <option value="">Select a job…</option>
            {allJobs?.map((j) => (
              <option key={j.id} value={j.id}>
                {j.title} {j.company_name ? `– ${j.company_name}` : ""}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-sm font-medium">Resume (optional)</span>
          <select
            value={resumeId}
            onChange={(e) =>
              setResumeId(e.target.value ? Number(e.target.value) : "")
            }
            className="w-full mt-1 p-2 border rounded bg-background"
          >
            <option value="">No resume</option>
            {resumes?.map((r) => (
              <option key={r.id} value={r.id}>
                {r.title}
              </option>
            ))}
          </select>
        </label>

        <Button
          disabled={jobId === "" || create.isPending}
          onClick={() => create.mutate()}
          className="flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          {create.isPending ? "Generating…" : "Generate Cover Letter"}
        </Button>
      </div>

      {letters?.length === 0 && (
        <p className="text-sm text-muted-foreground p-4 border rounded-lg">
          No cover letters yet.
        </p>
      )}

      <div className="space-y-4">
        {letters?.map((letter) => (
          <div key={letter.id} className="p-4 border rounded-lg space-y-2">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h3 className="font-semibold">
                  {letter.job_title ?? `Job #${letter.job_id}`}
                </h3>
                {letter.company_name && (
                  <p className="text-sm text-muted-foreground">
                    {letter.company_name}
                  </p>
                )}
                <p className="text-xs text-muted-foreground mt-1">
                  {letter.status} ·{" "}
                  {new Date(letter.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <button
                  onClick={() => {
                    setEditId(editId === letter.id ? null : letter.id);
                    setDraft(letter.content);
                  }}
                  className="p-2 rounded-md hover:bg-muted"
                  title="Edit"
                >
                  <Pencil className="h-4 w-4" />
                </button>
                <button
                  onClick={() => copyContent(letter)}
                  className="p-2 rounded-md hover:bg-muted"
                  title="Copy"
                >
                  {copied === letter.id ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
                <button
                  onClick={() => remove.mutate(letter.id)}
                  className="p-2 rounded-md hover:bg-muted"
                  title="Delete"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>

            <button
              onClick={() =>
                setExpanded(expanded === letter.id ? null : letter.id)
              }
              className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
            >
              <FileText className="h-4 w-4" />
              {expanded === letter.id ? "Hide letter" : "Preview letter"}
            </button>
            {expanded === letter.id &&
              (editId === letter.id ? (
                <div className="space-y-2 border-t pt-3">
                  <textarea
                    value={draft}
                    onChange={(e) => setDraft(e.target.value)}
                    rows={12}
                    className="w-full p-2 border rounded bg-background font-mono text-xs"
                  />
                  <div className="flex gap-2">
                    <Button
                      onClick={() =>
                        saveEdit.mutate({ id: letter.id, content: draft })
                      }
                      disabled={saveEdit.isPending}
                      className="flex items-center gap-2"
                    >
                      <Save className="h-4 w-4" />
                      Save changes
                    </Button>
                    <Button
                      variant="outline"
                      onClick={() => {
                        setEditId(null);
                        setDraft("");
                      }}
                      className="flex items-center gap-2"
                    >
                      <X className="h-4 w-4" />
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : (
                <pre className="text-sm whitespace-pre-wrap font-sans border-t pt-3 max-h-96 overflow-y-auto">
                  {letter.content}
                </pre>
              ))}
          </div>
        ))}
      </div>
    </div>
  );
}
