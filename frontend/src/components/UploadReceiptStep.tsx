import { useRef, useState } from "react";

type Props = {
  billDescription: string;
  isUploading: boolean;
  previewUrl: string | null;
  file: File | null;
  canParse: boolean;
  error: string | null;
  onBillDescriptionChange: (value: string) => void;
  onPickFile: (file: File | null) => void;
  onParseReceipt: () => void;
};

export default function UploadReceiptStep({
  billDescription,
  isUploading,
  previewUrl,
  file,
  canParse,
  error,
  onBillDescriptionChange,
  onPickFile,
  onParseReceipt,
}: Props) {
  const fileRef = useRef<HTMLInputElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  return (
    <div className="card formCard stack">
      <div>
        <h2 className="stepTitle">Step 1 — Upload receipt</h2>
        <div className="helper">Upload → Add bill description → Preview → Parse</div>
      </div>

      <label className="stack" style={{ gap: 6 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>Bill description</span>
        <input
          className="input"
          value={billDescription}
          onChange={(e) => onBillDescriptionChange(e.target.value)}
          placeholder="Dinner at Joe's"
          disabled={isUploading}
        />
      </label>

      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg"
        style={{ display: "none" }}
        disabled={isUploading}
        onChange={(e) => onPickFile(e.target.files?.[0] ?? null)}
      />

      <button
        className={`dropzone ${isDragging ? "dropzoneActive" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDragging(false);
          onPickFile(e.dataTransfer.files?.[0] ?? null);
        }}
        onClick={() => fileRef.current?.click()}
        disabled={isUploading}
      >
        <strong style={{ fontSize: 15 }}>Drop receipt image here</strong>
        <span className="helper">PNG or JPG • clear photo works best</span>
      </button>

      {previewUrl && (
        <div className="stack">
          <div className="previewFrame">
            <img src={previewUrl} alt="Receipt preview" />
          </div>
          <div>
            <div style={{ fontSize: 13 }}>{file?.name}</div>
            {file && <div className="helper">{(file.size / 1024).toFixed(1)} KB</div>}
          </div>
        </div>
      )}

      <button onClick={onParseReceipt} disabled={!canParse || !billDescription.trim()} className="btn btnPrimary">
        {isUploading ? "Parsing…" : "Parse receipt"}
      </button>

      {error && (
        <div className="alert">
          <strong>Couldn’t parse the receipt</strong>
          <div>{error}</div>
        </div>
      )}
    </div>
  );
}
