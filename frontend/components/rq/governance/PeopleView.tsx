"use client";

// La tabla de qué puede cada rol se pide a `/api/auth/catalog`: la UI no puede decir que un
// rol puede algo que el servidor le niega.
import { useState } from "react";
import { AsyncState, ErrorState } from "@/components/rq/AsyncState";
import { fmtDate } from "@/components/rq/ui";
import { api } from "@/lib/api/client";
import { useSession } from "@/lib/api/session";
import type { AuthCatalog, Role, User, UserPage } from "@/lib/api/types";
import { useResource } from "@/lib/api/useResource";

export default function PeopleView() {
  const { user: yo } = useSession();
  const users = useResource<UserPage>("users", () => api.users.list());
  const catalog = useResource<AuthCatalog>("auth-catalog", () => api.auth.catalog());

  if (!yo?.permissions?.includes("gestionar_usuarios")) {
    return (
      <p className="panel px-4 py-6 text-center text-[13px] text-ink-500">
        Solo un administrador gestiona las personas. Tu rol es {yo?.roleLabel ?? "—"}.
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <p className="max-w-3xl text-[13px] leading-5 text-ink-500">
        Cada persona entra con su propia cuenta y todo lo que hace queda registrado a su nombre:
        de eso dependen la auditoría, las firmas y el cuatro ojos del control de cambios. Cambiar
        un rol o desactivar una cuenta <strong>cierra sus sesiones abiertas</strong> en el acto.
      </p>

      <AsyncState resource={catalog}>
        {(cat) => (
          <>
            <NewUserForm roles={cat.roles} onCreated={() => users.reload()} />
            <AsyncState resource={users}>
              {(page) => (
                <PeopleTable
                  page={page}
                  catalog={cat}
                  myId={yo.id}
                  onChanged={() => users.reload()}
                />
              )}
            </AsyncState>
            <RolesTable catalog={cat} />
          </>
        )}
      </AsyncState>
    </div>
  );
}

function PeopleTable({
  page,
  catalog,
  myId,
  onChanged,
}: {
  page: UserPage;
  catalog: AuthCatalog;
  myId: string;
  onChanged: () => void;
}) {
  return (
    <div className="panel overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead className="bg-sunken text-left text-[11.5px] uppercase tracking-[0.06em] text-ink-500">
          <tr>
            <th className="px-4 py-2 font-medium">Persona</th>
            <th className="px-4 py-2 font-medium">Rol</th>
            <th className="px-4 py-2 font-medium">Estado</th>
            <th className="px-4 py-2 font-medium">Último acceso</th>
            <th className="px-4 py-2" />
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {page.items.map((persona) => (
            <PersonRow
              key={persona.id}
              persona={persona}
              roles={catalog.roles}
              esYo={persona.id === myId}
              onChanged={onChanged}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PersonRow({
  persona,
  roles,
  esYo,
  onChanged,
}: {
  persona: User;
  roles: Record<string, string>;
  esYo: boolean;
  onChanged: () => void;
}) {
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function actualizar(cambio: { role?: Role; active?: boolean }) {
    if (guardando) return;
    setGuardando(true);
    setError(null);
    try {
      await api.users.update(persona.id, cambio);
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setGuardando(false);
    }
  }

  return (
    <tr className={persona.active ? undefined : "opacity-60"}>
      <td className="px-4 py-2">
        <span className="flex items-center gap-2">
          <span
            aria-hidden
            className="flex h-6 w-6 items-center justify-center rounded-md bg-sunken font-mono text-[10px] font-semibold text-ink-700"
          >
            {persona.initials}
          </span>
          <span>
            <span className="block text-ink-900">
              {persona.name}
              {esYo && <span className="ml-1.5 chip chip-neutral">tú</span>}
            </span>
            <span className="block font-mono text-[11.5px] text-ink-400">{persona.email}</span>
          </span>
        </span>
      </td>
      <td className="px-4 py-2">
        <select
          value={persona.role}
          disabled={guardando}
          onChange={(e) => void actualizar({ role: e.target.value as Role })}
          aria-label={`Rol de ${persona.name}`}
          className="rounded-lg border border-line bg-surface px-2 py-1.5 text-[12.5px] outline-none focus:border-accent"
        >
          {Object.entries(roles).map(([valor, etiqueta]) => (
            <option key={valor} value={valor}>
              {etiqueta}
            </option>
          ))}
        </select>
        {persona.provider !== "local" && (
          <span className="ml-2 chip chip-neutral" title="Entra con el inicio de sesión corporativo">
            {persona.provider}
          </span>
        )}
      </td>
      <td className="px-4 py-2">
        {persona.locked ? (
          <span className="chip border-warn/30 bg-warn-soft text-warn">bloqueada</span>
        ) : persona.active ? (
          <span className="chip border-ok/30 bg-ok-soft text-ok">activa</span>
        ) : (
          <span className="chip chip-neutral">desactivada</span>
        )}
        {persona.mustChangePassword && (
          <span className="ml-1.5 chip chip-neutral" title="Tiene que cambiar la contraseña">
            contraseña inicial
          </span>
        )}
      </td>
      <td className="px-4 py-2 text-[12px] text-ink-500">
        {persona.lastLoginAt ? fmtDate(persona.lastLoginAt) : <span className="text-ink-400">nunca</span>}
      </td>
      <td className="px-4 py-2 text-right">
        {!esYo && (
          <button
            className="btn-ghost"
            disabled={guardando}
            onClick={() => void actualizar({ active: !persona.active })}
          >
            {persona.active ? "Desactivar" : "Activar"}
          </button>
        )}
        {error !== null && <ErrorState error={error} title="No se pudo actualizar" />}
      </td>
    </tr>
  );
}

function NewUserForm({
  roles,
  onCreated,
}: {
  roles: Record<string, string>;
  onCreated: () => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<Role>("desarrollador");
  const [password, setPassword] = useState("");
  const [creando, setCreando] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  async function crear(event: React.FormEvent) {
    event.preventDefault();
    if (creando || password.length < 12) return;
    setCreando(true);
    setError(null);
    try {
      const creada = await api.users.create({
        email: email.trim(),
        name: name.trim(),
        role,
        password,
        mustChangePassword: true,
      });
      setEmail("");
      setName("");
      setPassword("");
      setAviso(
        `Cuenta creada para ${creada.email}. Dale la contraseña por un canal seguro: tendrá que cambiarla al entrar.`,
      );
      onCreated();
    } catch (cause) {
      setError(cause);
    } finally {
      setCreando(false);
    }
  }

  return (
    <form className="panel space-y-3 p-4" onSubmit={crear}>
      <h2 className="panel-title">Dar de alta a una persona</h2>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">Correo</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">Nombre</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
        </label>
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">Rol</span>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as Role)}
            className="w-full rounded-lg border border-line bg-surface px-2 py-2 text-[13px] outline-none focus:border-accent"
          >
            {Object.entries(roles).map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </select>
        </label>
        <label className="space-y-1">
          <span className="block text-[12px] text-ink-500">Contraseña inicial</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            minLength={12}
            className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[12.5px] outline-none focus:border-accent"
          />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-primary" disabled={creando || !email || password.length < 12}>
          {creando ? "Creando…" : "Crear cuenta"}
        </button>
        <span className="text-[12px] text-ink-500">
          Al menos 12 caracteres. Una frase de varias palabras es más segura y más fácil de
          recordar que <span className="font-mono">Clave1!</span>
        </span>
      </div>
      {aviso && <p className="text-[12.5px] text-ok">{aviso}</p>}
      {error !== null && <ErrorState error={error} title="No se pudo crear la cuenta" />}
    </form>
  );
}

function RolesTable({ catalog }: { catalog: AuthCatalog }) {
  const permisos = Object.entries(catalog.permissions);
  return (
    <details className="panel p-4">
      <summary className="cursor-pointer text-[13px] text-ink-700">
        Qué puede hacer cada rol
      </summary>
      <div className="mt-3 overflow-x-auto">
        <table className="w-full text-[12.5px]">
          <thead className="text-left text-[11px] uppercase tracking-[0.06em] text-ink-500">
            <tr>
              <th className="py-2 pr-4 font-medium">Permiso</th>
              {Object.entries(catalog.roles).map(([valor, etiqueta]) => (
                <th key={valor} className="px-2 py-2 text-center font-medium">
                  {etiqueta}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {permisos.map(([permiso, etiqueta]) => (
              <tr key={permiso}>
                <td className="py-1.5 pr-4 text-ink-700">{etiqueta}</td>
                {Object.keys(catalog.roles).map((rol) => {
                  const tiene = (catalog.rolePermissions[rol] ?? []).includes(permiso);
                  return (
                    <td key={rol} className="px-2 py-1.5 text-center">
                      <span className={tiene ? "text-ok" : "text-ink-300"}>
                        {tiene ? "sí" : "—"}
                      </span>
                      <span className="sr-only">
                        {tiene ? "tiene el permiso" : "no tiene el permiso"}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
