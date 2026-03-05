import React, { createContext, useContext, useMemo } from "react";

export interface OctoAuthorConfig {
  /** Base URL of the OctoAuthor service (e.g., "http://localhost:8000") */
  baseUrl: string;
  /** API key for authentication (optional for public docs) */
  apiKey?: string;
  /** Path prefix for doc endpoints (default: "/api/v1") */
  apiPrefix?: string;
}

interface OctoAuthorContextValue {
  config: OctoAuthorConfig;
  fetchDoc: (tag: string) => Promise<string>;
}

const OctoAuthorContext = createContext<OctoAuthorContextValue | null>(null);

export function useOctoAuthor(): OctoAuthorContextValue {
  const ctx = useContext(OctoAuthorContext);
  if (!ctx) {
    throw new Error("useOctoAuthor must be used within an <OctoAuthorProvider>");
  }
  return ctx;
}

interface OctoAuthorProviderProps {
  config: OctoAuthorConfig;
  children: React.ReactNode;
}

export function OctoAuthorProvider({ config, children }: OctoAuthorProviderProps) {
  const value = useMemo(() => {
    const prefix = config.apiPrefix ?? "/api/v1";

    const fetchDoc = async (tag: string): Promise<string> => {
      const url = `${config.baseUrl}${prefix}/docs/${encodeURIComponent(tag)}`;
      const headers: Record<string, string> = {};
      if (config.apiKey) {
        headers["X-API-Key"] = config.apiKey;
      }
      const resp = await fetch(url, { headers });
      if (!resp.ok) {
        throw new Error(`Failed to fetch doc "${tag}": ${resp.status}`);
      }
      return resp.text();
    };

    return { config, fetchDoc };
  }, [config]);

  return (
    <OctoAuthorContext.Provider value={value}>
      {children}
    </OctoAuthorContext.Provider>
  );
}
