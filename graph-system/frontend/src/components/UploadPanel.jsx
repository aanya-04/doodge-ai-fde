import React, { useState, useRef } from "react";

export default function UploadPanel({ apiUrl, onSuccess }) {
  const [status, setStatus] = useState(null); // null | "uploading" | "success" | "error"
  const [message, setMessage] = useState("");
  const fileRef = useRef(null);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setStatus("uploading");
    setMessage("Processing dataset...");

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await fetch(`${apiUrl}/upload`, { method: "POST", body: form });
      const data = await res.json();

      if (res.ok && data.success) {
        setStatus("success");
        const s = data.graph_summary;
        setMessage(`✓ ${s?.total_nodes || 0} nodes, ${s?.total_edges || 0} edges`);
        onSuccess && onSuccess(data);
      } else {
        setStatus("error");
        setMessage(data.detail || "Upload failed");
      }
    } catch (e) {
      setStatus("error");
      setMessage("Connection error");
    }

    // Reset file input
    if (fileRef.current) fileRef.current.value = "";
  };

  return (
    <div className="upload-panel">
      <input
        ref={fileRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        style={{ display: "none" }}
        onChange={handleUpload}
      />
      <button
        className={`upload-btn ${status}`}
        onClick={() => fileRef.current?.click()}
        disabled={status === "uploading"}
      >
        {status === "uploading" ? (
          <><span className="upload-spinner" /> Loading...</>
        ) : (
          <><span>↑</span> Upload Dataset</>
        )}
      </button>
      {message && (
        <span className={`upload-msg ${status}`}>{message}</span>
      )}
    </div>
  );
}
