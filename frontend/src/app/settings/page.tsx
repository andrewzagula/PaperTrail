"use client";

import { useCallback, useEffect, useState } from "react";

import {
  Blank,
  Body,
  Button,
  Input,
  Menu,
  Notice,
  Num,
  PageHeader,
  PageSkeleton,
  Section,
  SectionHead,
  Segmented,
  StatusPill,
  Stepper,
  TopBar,
  WarnPanel,
  Working,
} from "@/components";
import type { MenuOption } from "@/components";
import { getApiErrorMessage } from "@/lib/api-errors";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Theme = "system" | "light" | "dark";
type Nav = "side" | "top";
type Density = "comfortable" | "compact";

const READING_MIN = 13;
const READING_MAX = 18;

const INHERIT = "__inherit__";

interface ProviderOption {
  value: string;
  label: string;
  requires: string[];
  missing_settings: string[];
  placeholder_settings: string[];
  ready: boolean;
}

interface WorkflowRow {
  field: string;
  label: string;
  hint: string;
  value: string;
  resolved: string;
  inherited: boolean;
}

interface CredentialCheck {
  status: "not_checked" | "ok" | "failed" | "skipped";
  detail: string;
}

interface ConfigStatus {
  provider: string;
  model: string;
  configured: boolean;
  missing_settings: string[];
  placeholder_settings: string[];
  unsupported: boolean;
  credential_check: CredentialCheck;
}

interface Health {
  status: string;
  credentials_verified: boolean;
  llm: ConfigStatus;
  embedding: ConfigStatus;
}

interface SettingsPayload {
  chat: { provider: string; model: string; providers: ProviderOption[] };
  embedding: { provider: string; model: string; providers: ProviderOption[] };
  workflows: WorkflowRow[];
  overridden: string[];
  health: Health;
}

/* Suggestions, not a catalogue. No provider exposes a reliable list, and a
   local Ollama model can be called anything at all, so every model field
   stays typeable and these only save some keystrokes. */
const MODEL_SUGGESTIONS: Record<string, string[]> = {
  openai: ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini", "gpt-4o", "o4-mini"],
  anthropic: [
    "claude-sonnet-4-5",
    "claude-opus-4-1",
    "claude-haiku-4-5-20251001",
  ],
  gemini: ["gemini-2.5-flash", "gemini-2.5-pro"],
  openai_compatible: [],
  ollama: ["llama3.2", "qwen2.5", "mistral"],
};

const EMBEDDING_SUGGESTIONS: Record<string, string[]> = {
  openai: ["text-embedding-3-small", "text-embedding-3-large"],
  sentence_transformers: ["all-MiniLM-L6-v2", "BAAI/bge-small-en-v1.5"],
};

function providerOptions(providers: ProviderOption[]): MenuOption[] {
  return providers.map((provider) => ({
    value: provider.value,
    label: provider.ready
      ? provider.label
      : `${provider.label} (needs ${provider.missing_settings.join(", ") || provider.placeholder_settings.join(", ")})`,
  }));
}

function SettingRow({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="set-row">
      <div>
        <p>{label}</p>
        {hint ? <p className="sub">{hint}</p> : null}
      </div>
      {children}
    </div>
  );
}

/** A model name: typeable, with the provider's usual names offered. */
function ModelField({
  value,
  suggestions,
  listId,
  label,
  disabled,
  onCommit,
}: {
  value: string;
  suggestions: string[];
  listId: string;
  label: string;
  disabled?: boolean;
  onCommit: (value: string) => void;
}) {
  const [draft, setDraft] = useState(value);

  useEffect(() => {
    setDraft(value);
  }, [value]);

  const commit = () => {
    const next = draft.trim();
    if (!next || next === value) {
      setDraft(value);
      return;
    }
    onCommit(next);
  };

  return (
    <>
      <Input
        value={draft}
        list={listId}
        aria-label={label}
        disabled={disabled}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            (event.target as HTMLInputElement).blur();
          }
          if (event.key === "Escape") {
            setDraft(value);
          }
        }}
      />
      <datalist id={listId}>
        {suggestions.map((suggestion) => (
          <option key={suggestion} value={suggestion} />
        ))}
      </datalist>
    </>
  );
}

export default function SettingsPage() {
  /* ---- Appearance. Local to this browser, applied on the spot. ---- */
  const [theme, setTheme] = useState<Theme>("system");
  const [nav, setNav] = useState<Nav>("side");
  const [density, setDensity] = useState<Density>("comfortable");
  const [reading, setReading] = useState(14);

  /* ---- Providers and models. Held by the server. ---- */
  const [config, setConfig] = useState<SettingsPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saved, setSaved] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [showWorkflows, setShowWorkflows] = useState(false);

  useEffect(() => {
    const stored = window.localStorage;
    const t = stored.getItem("pt-theme");
    if (t === "light" || t === "dark") setTheme(t);
    if (stored.getItem("pt-nav") === "top") setNav("top");
    if (stored.getItem("pt-density") === "compact") setDensity("compact");
    const r = Number(stored.getItem("pt-reading"));
    if (r >= READING_MIN && r <= READING_MAX) setReading(r);
  }, []);

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const res = await fetch(`${API_URL}/settings`);
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Failed to load settings."));
      }
      setConfig(await res.json());
    } catch (err) {
      setConfig(null);
      setLoadError(err instanceof Error ? err.message : "Failed to load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const change = async (patch: Record<string, string | null>) => {
    setSaving(true);
    setSaveError("");
    setSaved("");
    try {
      const res = await fetch(`${API_URL}/settings`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
      });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "That change was not saved."));
      }
      setConfig(await res.json());
      setSaved("Saved. It applies to the next run.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "That change was not saved.");
    } finally {
      setSaving(false);
    }
  };

  const verify = async () => {
    setVerifying(true);
    setSaveError("");
    setSaved("");
    try {
      const res = await fetch(`${API_URL}/settings/verify`, { method: "POST" });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "The check could not run."));
      }
      const health: Health = await res.json();
      setConfig((current) => (current ? { ...current, health } : current));
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "The check could not run.");
    } finally {
      setVerifying(false);
    }
  };

  const revert = async () => {
    setSaving(true);
    setSaveError("");
    setSaved("");
    try {
      const res = await fetch(`${API_URL}/settings/reset`, { method: "POST" });
      if (!res.ok) {
        throw new Error(await getApiErrorMessage(res, "Nothing was changed."));
      }
      setConfig(await res.json());
      setSaved("Back to whatever the .env file says.");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Nothing was changed.");
    } finally {
      setSaving(false);
    }
  };

  function applyTheme(value: Theme) {
    setTheme(value);
    const root = document.documentElement;
    if (value === "system") {
      root.removeAttribute("data-theme");
      window.localStorage.removeItem("pt-theme");
    } else {
      root.setAttribute("data-theme", value);
      window.localStorage.setItem("pt-theme", value);
    }
  }

  function applyNav(value: Nav) {
    setNav(value);
    const root = document.documentElement;
    if (value === "top") {
      root.setAttribute("data-nav", "top");
      window.localStorage.setItem("pt-nav", "top");
    } else {
      root.removeAttribute("data-nav");
      window.localStorage.removeItem("pt-nav");
    }
  }

  function applyDensity(value: Density) {
    setDensity(value);
    const root = document.documentElement;
    if (value === "compact") {
      root.setAttribute("data-density", "compact");
      window.localStorage.setItem("pt-density", "compact");
    } else {
      root.removeAttribute("data-density");
      window.localStorage.removeItem("pt-density");
    }
  }

  function applyReading(value: number) {
    setReading(value);
    document.documentElement.style.setProperty("--reading-size", `${value}px`);
    window.localStorage.setItem("pt-reading", String(value));
  }

  const health = config?.health;
  const check = health
    ? health.llm.credential_check.status === "ok" &&
      health.embedding.credential_check.status === "ok"
      ? "ok"
      : health.llm.credential_check.status === "failed" ||
          health.embedding.credential_check.status === "failed"
        ? "failed"
        : "not_checked"
    : "not_checked";

  return (
    <>
      <TopBar
        crumb={<b>Settings</b>}
        end={
          config ? (
            <>
              {check === "ok" ? (
                <StatusPill tone="ok">credentials work</StatusPill>
              ) : check === "failed" ? (
                <StatusPill tone="bad">credentials failed</StatusPill>
              ) : null}
              <Button variant="ghost" size="sm" onClick={verify} disabled={verifying}>
                {verifying ? "Checking" : "Verify credentials"}
              </Button>
            </>
          ) : undefined
        }
      />
      <Body>
        <PageHeader
          title="Settings"
          sub="Stored on this machine. Nothing here is sent anywhere except the provider you choose."
        />

        {saveError ? (
          <div style={{ marginTop: "var(--space-lg)" }}>
            <Notice tone="bad">{saveError}</Notice>
          </div>
        ) : saved ? (
          <div style={{ marginTop: "var(--space-lg)" }}>
            <Notice>{saved}</Notice>
          </div>
        ) : null}

        {loading ? (
          <Section>
            <PageSkeleton rows={5} />
          </Section>
        ) : loadError || !config ? (
          <Section>
            <Blank
              kind="Cannot reach the server"
              title="Providers and models are not editable right now"
              actions={<Button onClick={loadConfig}>Try again</Button>}
            >
              {loadError} PaperTrail talks to a local server on port 8000. Appearance
              below still works, because it never leaves this browser.
            </Blank>
          </Section>
        ) : (
          <>
            <div className="set-group">
              <h2>Providers</h2>
              <p className="hint">
                Chat and embeddings are configured separately. A change applies to
                the next run; nothing already finished is touched.
              </p>
              <div className="set-list">
                <SettingRow
                  label="Chat provider"
                  hint="Receives your prompts and paper excerpts"
                >
                  <Menu
                    label="Chat provider"
                    value={config.chat.provider}
                    disabled={saving}
                    options={providerOptions(config.chat.providers)}
                    onChange={(value) => change({ llm_provider: value })}
                  />
                </SettingRow>

                <SettingRow label="Chat model">
                  <ModelField
                    label="Chat model"
                    value={config.chat.model}
                    listId="chat-models"
                    disabled={saving}
                    suggestions={MODEL_SUGGESTIONS[config.chat.provider] ?? []}
                    onCommit={(value) => change({ llm_model: value })}
                  />
                </SettingRow>

                <SettingRow label="Embedding provider">
                  <Menu
                    label="Embedding provider"
                    value={config.embedding.provider}
                    disabled={saving}
                    options={providerOptions(config.embedding.providers)}
                    onChange={(value) => change({ embedding_provider: value })}
                  />
                </SettingRow>

                <SettingRow
                  label="Embedding model"
                  hint="Papers embedded with a different model stay put and read as stale until you re-embed them"
                >
                  <ModelField
                    label="Embedding model"
                    value={config.embedding.model}
                    listId="embedding-models"
                    disabled={saving}
                    suggestions={
                      EMBEDDING_SUGGESTIONS[config.embedding.provider] ?? []
                    }
                    onCommit={(value) => change({ embedding_model: value })}
                  />
                </SettingRow>
              </div>

              {health && !health.llm.configured ? (
                <WarnPanel title="The chat provider is not ready">
                  {health.llm.missing_settings.length > 0
                    ? `${health.llm.missing_settings.join(" and ")} ${health.llm.missing_settings.length === 1 ? "is" : "are"} not set. Add ${health.llm.missing_settings.length === 1 ? "it" : "them"} to the .env file at the top of the project and restart the server. Keys are deliberately not editable here.`
                    : health.llm.placeholder_settings.length > 0
                      ? `${health.llm.placeholder_settings.join(" and ")} still holds the example value from .env.example. Paste the real one in and restart the server.`
                      : "This provider is not one PaperTrail knows how to talk to."}
                </WarnPanel>
              ) : null}

              {health && health.llm.configured && !health.embedding.configured ? (
                <WarnPanel title="The embedding provider is not ready">
                  {health.embedding.missing_settings.join(" and ") ||
                    health.embedding.placeholder_settings.join(" and ")}{" "}
                  needs a value in the .env file. Chat still works; adding papers and
                  searching them does not.
                </WarnPanel>
              ) : null}

              {health && health.llm.configured && health.embedding.configured ? (
                check === "not_checked" ? (
                  <WarnPanel title="Credentials not checked">
                    The settings are present and well formed, but nothing has been
                    sent yet. Verifying spends a few tokens against each provider.
                  </WarnPanel>
                ) : check === "failed" ? (
                  <WarnPanel title="A provider rejected the test request">
                    {health.llm.credential_check.status === "failed"
                      ? health.llm.credential_check.detail
                      : health.embedding.credential_check.detail}
                  </WarnPanel>
                ) : null
              ) : null}
            </div>

            <div className="set-group">
              <div className="section-head">
                <h2>Per-step models</h2>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowWorkflows((current) => !current)}
                >
                  {showWorkflows ? "Hide" : "Show"}
                  <Num>{config.workflows.filter((w) => !w.inherited).length} set</Num>
                </Button>
              </div>
              <p className="hint">
                Each step can use a different model from the chat model. Leave a step
                following unless you have a reason: something cheap for ranking forty
                abstracts, something stronger for an implementation plan.
              </p>

              {showWorkflows ? (
                <div className="set-list">
                  {config.workflows.map((row) => {
                    const suggestions =
                      MODEL_SUGGESTIONS[config.chat.provider] ?? [];
                    const options: MenuOption[] = [
                      {
                        value: INHERIT,
                        label: `Follow the chat model (${config.chat.model})`,
                      },
                      ...Array.from(
                        new Set([...suggestions, ...(row.value ? [row.value] : [])]),
                      ).map((model) => ({ value: model, label: model })),
                    ];
                    return (
                      <SettingRow
                        key={row.field}
                        label={row.label}
                        hint={row.hint || undefined}
                      >
                        <Menu
                          label={row.label}
                          value={row.inherited ? INHERIT : row.value}
                          inherited={row.inherited}
                          disabled={saving}
                          options={options}
                          onChange={(value) =>
                            change({
                              [row.field]: value === INHERIT ? null : value,
                            })
                          }
                        />
                      </SettingRow>
                    );
                  })}
                </div>
              ) : null}

              {config.overridden.length > 0 ? (
                <div
                  style={{
                    marginTop: "var(--space-2xl)",
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-lg)",
                  }}
                >
                  <Num>
                    {config.overridden.length} setting
                    {config.overridden.length === 1 ? "" : "s"} changed here rather
                    than in .env
                  </Num>
                  <Button variant="ghost" size="sm" onClick={revert} disabled={saving}>
                    Revert them all
                  </Button>
                </div>
              ) : null}

              {saving ? (
                <div style={{ marginTop: "var(--space-lg)" }}>
                  <Working>Saving</Working>
                </div>
              ) : null}
            </div>
          </>
        )}

        <div className="set-group">
          <h2>Appearance</h2>
          <p className="hint">
            Applied immediately and remembered in this browser.
          </p>
          <div className="set-list">
            <SettingRow label="Theme">
              <Segmented
                label="Theme"
                value={theme}
                onChange={applyTheme}
                options={[
                  { value: "system", label: "System" },
                  { value: "light", label: "Light" },
                  { value: "dark", label: "Dark" },
                ]}
              />
            </SettingRow>

            <SettingRow
              label="Navigation"
              hint="Below 720px the navigation is horizontal either way"
            >
              <Segmented
                label="Navigation"
                value={nav}
                onChange={applyNav}
                options={[
                  { value: "side", label: "Sidebar" },
                  { value: "top", label: "Top bar" },
                ]}
              />
            </SettingRow>

            <SettingRow label="Density" hint="Row height and spacing throughout">
              <Segmented
                label="Density"
                value={density}
                onChange={applyDensity}
                options={[
                  { value: "comfortable", label: "Comfortable" },
                  { value: "compact", label: "Compact" },
                ]}
              />
            </SettingRow>

            <SettingRow
              label="Reading size"
              hint="Paper breakdown and chat only, not the interface"
            >
              <Stepper
                label="Reading size"
                value={reading}
                onChange={applyReading}
                min={READING_MIN}
                max={READING_MAX}
                format={(v) => `${v}px`}
              />
            </SettingRow>
          </div>
        </div>
      </Body>
    </>
  );
}
