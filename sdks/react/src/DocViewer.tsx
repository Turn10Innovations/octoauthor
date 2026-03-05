import React, { useEffect, useState } from "react";
import { useOctoAuthor } from "./OctoAuthorProvider";

interface DocViewerProps {
  /** Doc tag to display */
  tag: string;
  /** Custom CSS class for the container */
  className?: string;
  /** Render function for custom markdown rendering */
  renderMarkdown?: (markdown: string) => React.ReactNode;
  /** Loading placeholder */
  loadingContent?: React.ReactNode;
  /** Error placeholder */
  errorContent?: (error: string) => React.ReactNode;
}

export function DocViewer({
  tag,
  className,
  renderMarkdown,
  loadingContent,
  errorContent,
}: DocViewerProps) {
  const { fetchDoc } = useOctoAuthor();
  const [content, setContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    fetchDoc(tag)
      .then((md) => {
        if (!cancelled) {
          setContent(md);
          setLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message || "Failed to load documentation");
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [tag, fetchDoc]);

  if (loading) {
    return <>{loadingContent ?? <div className={className}>Loading...</div>}</>;
  }

  if (error) {
    return (
      <>
        {errorContent?.(error) ?? (
          <div className={className} role="alert">
            Error: {error}
          </div>
        )}
      </>
    );
  }

  if (!content) return null;

  if (renderMarkdown) {
    return <div className={className}>{renderMarkdown(content)}</div>;
  }

  // Default: render as preformatted text (users should provide renderMarkdown for rich display)
  return (
    <div className={className}>
      <pre style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{content}</pre>
    </div>
  );
}
