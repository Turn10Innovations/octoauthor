import React, { useCallback, useState } from "react";
import { DocViewer } from "./DocViewer";

interface HelpButtonProps {
  /** Doc tag to show when clicked */
  tag: string;
  /** Button label (default: "?") */
  label?: string;
  /** Panel title */
  title?: string;
  /** Custom CSS class for the button */
  buttonClassName?: string;
  /** Custom CSS class for the panel */
  panelClassName?: string;
  /** Render function for custom markdown rendering */
  renderMarkdown?: (markdown: string) => React.ReactNode;
  /** Panel position (default: "right") */
  position?: "right" | "left" | "bottom";
}

const defaultStyles = {
  button: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    border: "1px solid #ccc",
    background: "#f8f9fa",
    cursor: "pointer",
    fontSize: "14px",
    fontWeight: 600,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
  } as React.CSSProperties,
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.3)",
    zIndex: 9998,
  } as React.CSSProperties,
  panel: {
    position: "fixed",
    top: 0,
    right: 0,
    width: "400px",
    height: "100vh",
    background: "#fff",
    boxShadow: "-2px 0 8px rgba(0,0,0,0.15)",
    zIndex: 9999,
    overflow: "auto",
    padding: "24px",
  } as React.CSSProperties,
  panelHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: "16px",
    borderBottom: "1px solid #eee",
    paddingBottom: "12px",
  } as React.CSSProperties,
  closeButton: {
    background: "none",
    border: "none",
    fontSize: "20px",
    cursor: "pointer",
    padding: "4px 8px",
  } as React.CSSProperties,
};

export function HelpButton({
  tag,
  label = "?",
  title = "Help",
  buttonClassName,
  panelClassName,
  renderMarkdown,
  position = "right",
}: HelpButtonProps) {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => setOpen((prev) => !prev), []);
  const close = useCallback(() => setOpen(false), []);

  const panelStyle: React.CSSProperties = {
    ...defaultStyles.panel,
    ...(position === "left" ? { left: 0, right: "auto" } : {}),
    ...(position === "bottom"
      ? { top: "auto", bottom: 0, width: "100%", height: "50vh" }
      : {}),
  };

  return (
    <>
      <button
        type="button"
        onClick={toggle}
        className={buttonClassName}
        style={buttonClassName ? undefined : defaultStyles.button}
        aria-label={`Open help for ${tag}`}
        aria-expanded={open}
      >
        {label}
      </button>

      {open && (
        <>
          <div style={defaultStyles.overlay} onClick={close} aria-hidden="true" />
          <div
            role="dialog"
            aria-label={title}
            className={panelClassName}
            style={panelClassName ? undefined : panelStyle}
          >
            <div style={defaultStyles.panelHeader}>
              <strong>{title}</strong>
              <button
                type="button"
                onClick={close}
                style={defaultStyles.closeButton}
                aria-label="Close help panel"
              >
                &times;
              </button>
            </div>
            <DocViewer
              tag={tag}
              renderMarkdown={renderMarkdown}
              loadingContent={<p>Loading help...</p>}
              errorContent={(err) => <p style={{ color: "red" }}>{err}</p>}
            />
          </div>
        </>
      )}
    </>
  );
}
