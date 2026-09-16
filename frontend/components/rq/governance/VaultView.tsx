"use client";

// Esta pantalla no puede enseñar un valor: el endpoint que lo devolvería no existe.
import { useState } from "react";
import { AsyncState, ErrorState } from "@/components/rq/AsyncState";
import { fmtDate } from "@/components/rq/ui";
import { api } from "@/lib/api/client";
import type { Secret, SecretKind, SecretPage } from "@/lib/api/types";
import { useResource } from "@/lib/api/useResource";

const KINDS: { kind: SecretKind; label: string; placeholder: string; ayuda: string }[] = [
  {
    kind: "git_token",
    label: "Token de repositorio",
    placeholder: "github.com",
    ayuda: "Host del repositorio. Lo usa el agente Código para clonar repositorios privados.",
  },
  {
    kind: "site_credential",
    label: "Credencial de sitio",
    placeholder: "https://portal.acme.local",
    ayuda: "URL del sitio que prueba el agente UI/UX.",
  },
  {
    kind: "llm_api_key",
    label: "Clave de proveedor de IA",
    placeholder: "anthropic",
    ayuda: "Nombre del proveedor.",
  },
  {
    kind: "azure_devops",
    label: "Credencial de Azure DevOps",
    placeholder: "dev.azure.com/acme",
    ayuda: "Organización de Azure DevOps.",
  },
];

const STATUS_CLASS: Record<string, string> = {
  activo: "border-ok/30 bg-ok-soft text-ok",
  caducado: "border-warn/30 bg-warn-soft text-warn",
  revocado: "border-line bg-sunken text-ink-400",
};

export default function VaultView() {
  const secrets = useResource<SecretPage>("secrets", () => api.secrets.list());

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-[13px] leading-5 text-ink-500">
        Aquí se guardan las credenciales que necesitan los agentes: el token de un repositorio
        privado, el usuario del sitio que se prueba, la clave de un proveedor de IA. Se guardan
        cifradas en el servidor y <strong>no hay forma de volver a verlas</strong>: ni desde esta
        pantalla ni desde la API. Lo que se ve es qué hay puesto, quién lo puso y cuándo se usó.
      </p>

      <SaveForm onSaved={() => secrets.reload()} />

      <AsyncState resource={secrets}>
        {(page) =>
          page.items.length === 0 ? (
            <p className="panel px-4 py-6 text-center text-[13px] text-ink-500">
              No hay ningún secreto guardado. Los repositorios privados y el agente UI/UX lo
              necesitan.
            </p>
          ) : (
            <SecretsTable page={page} onChanged={() => secrets.reload()} />
          )
        }
      </AsyncState>
    </div>
  );
}

function SecretsTable({ page, onChanged }: { page: SecretPage; onChanged: () => void }) {
  return (
    <div className="panel overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead className="bg-sunken text-left text-[11.5px] uppercase tracking-[0.06em] text-ink-500">
          <tr>
            <th className="px-4 py-2 font-medium">Tipo</th>
            <th className="px-4 py-2 font-medium">Se aplica a</th>
            <th className="px-4 py-2 font-medium">Ámbito</th>
            <th className="px-4 py-2 font-medium">Estado</th>
            <th className="px-4 py-2 font-medium">Guardado</th>
            <th className="px-4 py-2 font-medium">Último uso</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {page.items.map((secret) => (
            <SecretRow key={secret.id} secret={secret} onChanged={onChanged} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SecretRow({ secret, onChanged }: { secret: Secret; onChanged: () => void }) {
  const [revocando, setRevocando] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function revocar() {
    if (revocando) return;
    setRevocando(true);
    setError(null);
    try {
      await api.secrets.revoke(secret.id, "emanuel");
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setRevocando(false);
    }
  }

  return (
    <tr className={secret.status === "revocado" ? "opacity-60" : undefined}>
      <td className="px-4 py-2 text-ink-900">{secret.kindLabel}</td>
      <td className="px-4 py-2">
        <span className="font-mono text-[12.5px] text-ink-900">{secret.name}</span>
        {secret.username && (
          <span className="ml-2 text-[12px] text-ink-500">usuario {secret.username}</span>
        )}
        <span className="ml-2 font-mono text-[11.5px] text-ink-400">{secret.hint}</span>
      </td>
      <td className="px-4 py-2 text-[12.5px] text-ink-500">
        {secret.scope || "toda la organización"}
      </td>
      <td className="px-4 py-2">
        <span className={`chip ${STATUS_CLASS[secret.status] ?? "chip-neutral"}`}>
          {secret.status}
        </span>
      </td>
      <td className="px-4 py-2 text-[12px] text-ink-500">
        {fmtDate(secret.createdAt)}
        <span className="block text-[11.5px] text-ink-400">por {secret.createdBy}</span>
      </td>
      <td className="px-4 py-2 text-[12px] text-ink-500">
        {secret.lastUsedAt ? (
          <>
            {fmtDate(secret.lastUsedAt)}
            <span className="block text-[11.5px] text-ink-400">{secret.uses} uso(s)</span>
          </>
        ) : (
          <span className="text-ink-400">sin usar</span>
        )}
      </td>
      <td className="px-4 py-2 text-right">
        {secret.status !== "revocado" && (
          <button className="btn-ghost" onClick={revocar} disabled={revocando}>
            {revocando ? "Revocando…" : "Revocar"}
          </button>
        )}
        {error !== null && <ErrorState error={error} title="No se pudo revocar" />}
      </td>
    </tr>
  );
}

function SaveForm({ onSaved }: { onSaved: () => void }) {
  const [kind, setKind] = useState<SecretKind>("git_token");
  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [value, setValue] = useState("");
  const [scope, setScope] = useState("");
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [guardado, setGuardado] = useState<string | null>(null);

  const actual = KINDS.find((k) => k.kind === kind);

  async function guardar(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || value.trim().length < 8 || guardando) return;
    setGuardando(true);
    setError(null);
    try {
      const secreto = await api.secrets.save({
        kind,
        name: name.trim(),
        value: value.trim(),
        username: username.trim(),
        scope: scope.trim(),
      });
      // El valor se borra del formulario en cuanto sale: no se queda en la memoria de la página.
      setValue("");
      setName("");
      setUsername("");
      setGuardado(`${secreto.kindLabel} para ${secreto.name} guardado (${secreto.hint}).`);
      onSaved();
    } catch (cause) {
      setError(cause);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <form className="panel space-y-3 p-4" onSubmit={guardar}>
      <h2 className="panel-title">Guardar o rotar un secreto</h2>
      <div className="grid gap-2 sm:grid-cols-2">
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">Tipo</span>
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value as SecretKind)}
            className="w-full rounded-lg border border-line bg-surface px-2 py-2 text-[13px] outline-none focus:border-accent"
          >
            {KINDS.map((option) => (
              <option key={option.kind} value={option.kind}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">Se aplica a</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder={actual?.placeholder}
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[12.5px] outline-none focus:border-accent"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">Usuario (opcional)</span>
          <input
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="x-access-token"
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">
            Ámbito (vacío = toda la organización)
          </span>
          <input
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            placeholder="REQ-001"
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[12.5px] outline-none focus:border-accent"
          />
        </label>
      </div>
      <label className="block space-y-1">
        <span className="block text-[12px] text-ink-500">Secreto</span>
        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="se guarda cifrado y no se vuelve a mostrar"
          autoComplete="new-password"
          className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[12.5px] outline-none focus:border-accent"
        />
      </label>
      <p className="text-[11.5px] text-ink-400">{actual?.ayuda}</p>
      <div className="flex items-center gap-3">
        <button className="btn-primary" disabled={guardando || !name.trim() || value.trim().length < 8}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
        <span className="text-[12px] text-ink-500">
          Guardar otra vez el mismo tipo y nombre lo <strong>rota</strong>: sustituye el valor.
        </span>
      </div>
      {guardado && <p className="text-[12.5px] text-ok">{guardado}</p>}
      {error !== null && <ErrorState error={error} title="No se pudo guardar el secreto" />}
    </form>
  );
}
