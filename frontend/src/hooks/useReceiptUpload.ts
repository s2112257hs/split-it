import { useEffect, useState } from "react";

type UseReceiptUploadResult = {
  file: File | null;
  previewUrl: string | null;
  isUploading: boolean;
  error: string | null;
  canParse: boolean;
  pickFile: (nextFile: File | null) => void;
  beginUpload: () => void;
  endUpload: () => void;
  setError: (message: string | null) => void;
  resetUploadState: () => void;
};

export function useReceiptUpload(): UseReceiptUploadResult {
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canParse = !!file && !isUploading;

  function pickFile(nextFile: File | null) {
    setFile(nextFile);
    setError(null);

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setPreviewUrl(nextFile ? URL.createObjectURL(nextFile) : null);
  }

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  function beginUpload() {
    setIsUploading(true);
    setError(null);
  }

  function endUpload() {
    setIsUploading(false);
  }

  function resetUploadState() {
    setFile(null);
    setError(null);
    setIsUploading(false);

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setPreviewUrl(null);
  }

  return {
    file,
    previewUrl,
    isUploading,
    error,
    canParse,
    pickFile,
    beginUpload,
    endUpload,
    setError,
    resetUploadState,
  };
}
