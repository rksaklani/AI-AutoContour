import { useEffect, useRef, useState } from "react";

import { useCreateStudy, useUploadDicom } from "@/api/studies";
import { Spinner } from "@/components/ui";

export function UploadDialog({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: (studyId: string) => void;
}) {
  const createStudy = useCreateStudy();
  const uploadDicom = useUploadDicom();
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  // `webkitdirectory` isn't in the standard input typings; set it imperatively.
  useEffect(() => {
    if (folderInput.current) {
      folderInput.current.setAttribute("webkitdirectory", "");
      folderInput.current.setAttribute("directory", "");
    }
  }, []);

  const [patientName, setPatientName] = useState("");
  const [modality, setModality] = useState("CT");
  const [bodyPart, setBodyPart] = useState("Chest");
  const [description, setDescription] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  function onDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const dropped = Array.from(e.dataTransfer.files ?? []);
    if (dropped.length > 0) setFiles(dropped);
  }

  async function submit() {
    setError(null);
    setBusy(true);
    try {
      const study = await createStudy.mutateAsync({
        patient_name: patientName,
        modality,
        body_part: bodyPart,
        description,
      } as never);
      if (files.length > 0) {
        await uploadDicom.mutateAsync({ studyId: study.id, files });
      }
      onCreated(study.id);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Failed to create study");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="panel w-full max-w-lg p-6">
        <h2 className="mb-4 text-lg font-semibold text-white">New study</h2>

        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2">
            <label className="mb-1 block text-xs text-slate-400">Patient name</label>
            <input className="input" value={patientName} onChange={(e) => setPatientName(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Modality</label>
            <select className="input" value={modality} onChange={(e) => setModality(e.target.value)}>
              {["CT", "MR", "PET", "CR", "DX", "US"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs text-slate-400">Body part</label>
            <input className="input" value={bodyPart} onChange={(e) => setBodyPart(e.target.value)} />
          </div>
          <div className="col-span-2">
            <label className="mb-1 block text-xs text-slate-400">Description</label>
            <input className="input" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
        </div>

        <div className="mt-4">
          <label className="mb-1 block text-xs text-slate-400">
            DICOM files or folder (CT, MR, PET, X-Ray, US, RTSTRUCT)
          </label>
          {/* No `accept` filter: DICOM files often have no extension, so we validate by
              content on the server rather than restricting the picker. */}
          <input
            ref={fileInput}
            type="file"
            multiple
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            className="hidden"
          />
          <input
            ref={folderInput}
            type="file"
            multiple
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
            className="hidden"
          />
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={onDrop}
            className={`flex flex-col items-center gap-2 rounded-md border border-dashed p-4 transition-colors ${
              dragging ? "border-brand-500 bg-brand-600/10" : "border-surface-600 bg-surface-800/40"
            }`}
          >
            <p className="text-xs text-slate-400">Drag &amp; drop DICOM files here</p>
            <div className="flex gap-2">
              <button type="button" className="btn-ghost text-xs" onClick={() => fileInput.current?.click()}>
                Choose files
              </button>
              <button type="button" className="btn-ghost text-xs" onClick={() => folderInput.current?.click()}>
                Choose folder
              </button>
            </div>
          </div>
          {files.length > 0 && (
            <p className="mt-1 text-xs text-slate-500">{files.length} file(s) selected</p>
          )}
          <p className="mt-1 text-[11px] text-slate-600">
            Extension-independent: non-DICOM files are skipped automatically.
          </p>
        </div>

        {error && <p className="mt-3 text-sm text-red-400">{error}</p>}

        <div className="mt-6 flex justify-end gap-2">
          <button className="btn-ghost" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button className="btn-primary" onClick={submit} disabled={busy}>
            {busy && <Spinner />}
            Create &amp; upload
          </button>
        </div>
      </div>
    </div>
  );
}
