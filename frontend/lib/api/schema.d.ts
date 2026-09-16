/**
 * Generado desde backend/openapi.json. No editar a mano.
 * Regenerar con: npm run api:types
 */

export interface paths {
    "/api/audit": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Index */
        get: operations["index_api_audit_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/audit/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Verify
         * @description Recalcula la cadena y dice si alguien tocó una entrada.
         */
        get: operations["verify_api_audit_verify_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Catalog
         * @description Roles y permisos. La UI los consulta en vez de copiar la tabla.
         */
        get: operations["catalog_api_auth_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/login": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Login
         * @description Inicia sesión.
         *
         *     Con credenciales incorrectas responde siempre lo mismo, exista o no el correo: decir «ese
         *     usuario no existe» le confirma a quien prueba direcciones cuáles son válidas.
         */
        post: operations["login_api_auth_login_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Logout
         * @description Cierra la sesión. Es idempotente: sin cookie no falla.
         */
        post: operations["logout_api_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Me
         * @description Quién soy. Sin sesión responde `authenticated: false`, no un error.
         *
         *     Es a propósito: la aplicación lo llama al cargar para decidir si enseña el login o la
         *     aplicación, y un 401 ahí ensuciaría la consola del navegador en cada arranque.
         */
        get: operations["me_api_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/auth/password": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Change Password
         * @description Cambia la contraseña propia y cierra las demás sesiones.
         */
        put: operations["change_password_api_auth_password_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/catalog/agents": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Agents
         * @description Definición de cada agente. El esquema y las herramientas son de solo lectura.
         */
        get: operations["agents_api_catalog_agents_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/catalog/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Models
         * @description Modelos y precios estimados por proveedor, con la señal de BAA.
         */
        get: operations["models_api_catalog_models_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/catalog/profiles": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Profiles
         * @description Perfiles efectivos: los globales, o los del requerimiento si se indica.
         */
        get: operations["profiles_api_catalog_profiles_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Health
         * @description Estado y configuración efectiva. Nunca devuelve el valor de una credencial.
         */
        get: operations["health_api_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/requirements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Index
         * @description Lista paginada con lo que la tabla necesita: última ejecución y agentes planificados.
         *
         *     Se consulta la última ejecución y el plan de cada requerimiento de la página (una consulta
         *     por fila). Con páginas de 50 es asumible; si el Monitor lo nota, se agrupa en una sola
         *     consulta (ORQ-29).
         */
        get: operations["index_api_requirements_get"];
        put?: never;
        /** Create */
        post: operations["create_api_requirements_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/requirements/{requirement_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["detail_api_requirements__requirement_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/requirements/{requirement_id}/attachments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Add Attachment
         * @description Adjunta un repositorio o un archivo al requerimiento.
         *
         *     Guarda el tipo y el nombre; el archivo en sí, cifrado y con retención, es ORQ-19.
         */
        post: operations["add_attachment_api_requirements__requirement_id__attachments_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/requirements/{requirement_id}/phi": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Classify Phi
         * @description Clasifica el requerimiento. Con PHI, Privacidad pasa a ser obligatorio.
         */
        put: operations["classify_phi_api_requirements__requirement_id__phi_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/requirements/{requirement_id}/plan": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Plan */
        get: operations["get_plan_api_requirements__requirement_id__plan_get"];
        /**
         * Update Plan
         * @description Aplica lo que la persona activó o desactivó. Lo obligatorio no se puede quitar.
         */
        put: operations["update_plan_api_requirements__requirement_id__plan_put"];
        /**
         * Suggest Plan
         * @description Sugiere el plan con las reglas deterministas. El usuario decide después.
         *
         *     Con `assisted=true` el Orquestador revisa la propuesta; no puede saltarse lo obligatorio.
         */
        post: operations["suggest_plan_api_requirements__requirement_id__plan_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/requirements/{requirement_id}/repo": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Connect Repo
         * @description Conecta el repositorio del cambio y fija el commit que se va a revisar.
         *
         *     El clonado y la credencial se quedan en el servidor: la respuesta solo lleva la ficha pública
         *     del repositorio (rama, rango, commits y archivos del cambio).
         */
        post: operations["connect_repo_api_requirements__requirement_id__repo_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/requirements/{requirement_id}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_api_requirements__requirement_id__runs_get"];
        put?: never;
        /**
         * Start Run
         * @description Lanza la revisión y devuelve de inmediato: la ejecución sigue en segundo plano.
         */
        post: operations["start_run_api_requirements__requirement_id__runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["detail_api_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Cancel
         * @description Detiene la ejecución: corta las llamadas en curso y cierra los agentes pendientes.
         */
        post: operations["cancel_api_runs__run_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/deliverables": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Deliverables */
        get: operations["deliverables_api_runs__run_id__deliverables_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Trace
         * @description Traza persistida. El canal en vivo con replay llega en ORQ-17.
         */
        get: operations["trace_api_runs__run_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/secrets": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * Index
         * @description Qué secretos hay configurados: tipo, a qué se aplican, quién y cuándo. **Sin valores.**
         */
        get: operations["index_api_secrets_get"];
        put?: never;
        /**
         * Save
         * @description Guarda o **rota** un secreto.
         *
         *     Guardar otra vez el mismo tipo, nombre y ámbito sustituye el valor y levanta una revocación
         *     anterior: es la rotación. La respuesta son metadatos.
         */
        post: operations["save_api_secrets_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/secrets/{secret_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        /**
         * Revoke
         * @description Revoca un secreto: deja de funcionar de inmediato y su valor se borra de la base.
         */
        delete: operations["revoke_api_secrets__secret_id__delete"];
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/users": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Index */
        get: operations["index_api_users_get"];
        put?: never;
        /** Create */
        post: operations["create_api_users_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/users/{user_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /**
         * Update
         * @description Cambia rol, nombre o si la cuenta está activa.
         *
         *     Desactivar o cambiar de rol **cierra las sesiones abiertas** de esa persona: si no, el cambio
         *     no surtiría efecto hasta que cerrara sesión por su cuenta.
         */
        put: operations["update_api_users__user_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** AgentCatalogOut */
        AgentCatalogOut: {
            /** Agents */
            agents: {
                [key: string]: components["schemas"]["AgentDefinitionOut"];
            };
            /** All */
            all: string[];
            /** Order */
            order: string[];
        };
        /** AgentDefinitionOut */
        AgentDefinitionOut: {
            /** Dependson */
            dependsOn?: string[];
            /** Id */
            id: string;
            /** Label */
            label: string;
            /** Optional */
            optional: boolean;
            /** Outputschema */
            outputSchema: {
                [key: string]: unknown;
            };
            /**
             * Processesphi
             * @default true
             */
            processesPhi: boolean;
            /** Requiresattachment */
            requiresAttachment?: string | null;
            /** Role */
            role: string;
            /** Short */
            short: string;
            /** Tools */
            tools?: string[];
        };
        /** AgentExecutionOut */
        AgentExecutionOut: {
            /** Agentid */
            agentId: string;
            /** Calls */
            calls?: components["schemas"]["LLMCallOut"][];
            /**
             * Error
             * @default
             */
            error: string;
            /** Finishedat */
            finishedAt?: string | null;
            /**
             * Reason
             * @default
             */
            reason: string;
            /** Startedat */
            startedAt?: string | null;
            /** Status */
            status: string;
            usage: components["schemas"]["UsageOut"];
        };
        /**
         * AgentId
         * @description Agentes gobernados. `CHAT` no participa en el flujo de revisión.
         * @enum {string}
         */
        AgentId: "orchestrator" | "code" | "tests" | "kiuwan" | "sql" | "uiux" | "privacy" | "vtr" | "verdict" | "chat";
        /** AgentProfileOut */
        AgentProfileOut: {
            /** Agentid */
            agentId: string;
            /** Maxsteps */
            maxSteps: number;
            /** Model */
            model: string;
            /** Promptversion */
            promptVersion: number;
            /** Provider */
            provider: string;
            /** Systemprompt */
            systemPrompt: string;
            /** Taskprompt */
            taskPrompt: string;
            /** Temperature */
            temperature: number;
            /** Versions */
            versions?: components["schemas"]["PromptVersionOut"][];
        };
        /**
         * ApiError
         * @description Forma única de todos los errores. La UI la traduce a un mensaje por `code`.
         */
        ApiError: {
            /**
             * Code
             * @description Identificador estable del error, p. ej. NotFoundError
             */
            code: string;
            /**
             * Detail
             * @description Datos extra del error
             */
            detail?: {
                [key: string]: unknown;
            } | null;
            /**
             * Message
             * @description Mensaje en español, ya legible
             */
            message: string;
        };
        /** AttachmentIn */
        AttachmentIn: {
            /**
             * Detail
             * @default
             */
            detail: string;
            kind: components["schemas"]["AttachmentKind"];
            /** Name */
            name: string;
        };
        /**
         * AttachmentKind
         * @enum {string}
         */
        AttachmentKind: "repo" | "vtr_template" | "kiuwan_csv" | "sql";
        /** AttachmentOut */
        AttachmentOut: {
            /**
             * Addedat
             * Format: date-time
             */
            addedAt: string;
            /** Addedby */
            addedBy: string;
            /**
             * Detail
             * @default
             */
            detail: string;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Name */
            name: string;
            repo?: components["schemas"]["RepoOut"] | null;
        };
        /** AuditEntryOut */
        AuditEntryOut: {
            /** Action */
            action: string;
            /** Actor */
            actor: string;
            /**
             * At
             * Format: date-time
             */
            at: string;
            /**
             * Detail
             * @default
             */
            detail: string;
            /** Hash */
            hash: string;
            /** Prevhash */
            prevHash: string;
            /** Seq */
            seq: number;
            /** Target */
            target: string;
        };
        /** AuditPage */
        AuditPage: {
            /** Items */
            items: components["schemas"]["AuditEntryOut"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /** AuditVerificationOut */
        AuditVerificationOut: {
            /** Brokenat */
            brokenAt?: number | null;
            /** Entries */
            entries: number;
            /** Valid */
            valid: boolean;
        };
        /**
         * CatalogOut
         * @description Roles y permisos, para que la UI no duplique la tabla del dominio.
         */
        CatalogOut: {
            /** Permissions */
            permissions: {
                [key: string]: string;
            };
            /** Rolepermissions */
            rolePermissions: {
                [key: string]: string[];
            };
            /** Roles */
            roles: {
                [key: string]: string;
            };
        };
        /** ChangeMapEntryOut */
        ChangeMapEntryOut: {
            /**
             * Added
             * @default 0
             */
            added: number;
            /** Change */
            change: string;
            /** Criteria */
            criteria?: number[];
            /** File */
            file: string;
            /**
             * Removed
             * @default 0
             */
            removed: number;
            /** Symbols */
            symbols?: string[];
        };
        /** ChangePasswordBody */
        ChangePasswordBody: {
            /** Current */
            current: string;
            /** New */
            new: string;
        };
        /** ClassifyPhiIn */
        ClassifyPhiIn: {
            phi: components["schemas"]["PhiClassification"];
        };
        /** CodeReportOut */
        CodeReportOut: {
            /** Changemap */
            changeMap?: components["schemas"]["ChangeMapEntryOut"][];
            /** Findings */
            findings?: components["schemas"]["FindingOut"][];
            /**
             * Stack
             * @default
             */
            stack: string;
            /** Summary */
            summary: string;
        };
        /**
         * ConnectRepoIn
         * @description Repositorio a revisar. **La credencial no viaja aquí**: la pone el servidor (ORQ-18).
         */
        ConnectRepoIn: {
            /**
             * Base
             * @description Rama o commit base. Vacío = últimos «lastCommits» commits
             * @default
             */
            base: string;
            /**
             * Branch
             * @description Rama del desarrollo. Vacío = la rama por defecto
             * @default
             */
            branch: string;
            /**
             * Lastcommits
             * @description Cuántos commits atrás comparar si no se da base
             * @default 1
             */
            lastCommits: number;
            /**
             * Url
             * @description URL de clonado (HTTPS o SSH)
             */
            url: string;
        };
        /**
         * CreateRequirementIn
         * @description El responsable no viene aquí: es el usuario autenticado (ORQ-5).
         */
        CreateRequirementIn: {
            /** Acceptancecriteria */
            acceptanceCriteria?: string[];
            /** Attachments */
            attachments?: components["schemas"]["AttachmentIn"][];
            /**
             * Description
             * @default
             */
            description: string;
            /** @default desconocido */
            phi: components["schemas"]["PhiClassification"];
            /** Title */
            title: string;
        };
        /** CreateUserIn */
        CreateUserIn: {
            /** Email */
            email: string;
            /**
             * Mustchangepassword
             * @default true
             */
            mustChangePassword: boolean;
            /**
             * Name
             * @default
             */
            name: string;
            /** Password */
            password: string;
            role: components["schemas"]["Role"];
        };
        /**
         * DeliverablesOut
         * @description Un informe por agente. `null` = ese agente no se ejecutó (y `missing` dice por qué).
         */
        DeliverablesOut: {
            code?: components["schemas"]["CodeReportOut"] | null;
            /** Findings */
            findings?: components["schemas"]["FindingOut"][];
            kiuwan?: components["schemas"]["KiuwanReportOut"] | null;
            /** Missing */
            missing?: {
                [key: string]: string;
            };
            privacy?: components["schemas"]["PrivacyReportOut"] | null;
            sql?: components["schemas"]["SqlReportOut"] | null;
            tests?: components["schemas"]["TestsReportOut"] | null;
            uiux?: components["schemas"]["UiuxReportOut"] | null;
            verdict?: components["schemas"]["VerdictReportOut"] | null;
            vtr?: components["schemas"]["VtrReportOut"] | null;
        };
        /** FindingOut */
        FindingOut: {
            /** Detail */
            detail: string;
            /**
             * File
             * @default
             */
            file: string;
            /** Id */
            id: string;
            /** Line */
            line?: number | null;
            /** Safeguard */
            safeguard?: string | null;
            /** Severity */
            severity: string;
            /** Source */
            source: string;
            /**
             * Suggestion
             * @default
             */
            suggestion: string;
            /** Title */
            title: string;
            /**
             * Url
             * @default
             */
            url: string;
        };
        /** GeneratedTestOut */
        GeneratedTestOut: {
            /**
             * Code
             * @default
             */
            code: string;
            /** Criterion */
            criterion?: number | null;
            /**
             * Durationms
             * @default 0
             */
            durationMs: number;
            /**
             * Failurereason
             * @default
             */
            failureReason: string;
            /** File */
            file: string;
            /**
             * Kind
             * @default unitario
             */
            kind: string;
            /** Name */
            name: string;
            /** Status */
            status: string;
        };
        /** HealthOut */
        HealthOut: {
            /** Config */
            config: {
                [key: string]: unknown;
            };
            /** Database */
            database: string;
            /** Status */
            status: string;
            /** Version */
            version: string;
        };
        /** KiuwanDefectOut */
        KiuwanDefectOut: {
            /**
             * Category
             * @default
             */
            category: string;
            /**
             * Falsepositive
             * @default false
             */
            falsePositive: boolean;
            /** File */
            file: string;
            /** Line */
            line?: number | null;
            /**
             * Note
             * @default
             */
            note: string;
            /**
             * Rule
             * @default
             */
            rule: string;
            /** Ruleid */
            ruleId: string;
            /** Severity */
            severity: string;
        };
        /** KiuwanReportOut */
        KiuwanReportOut: {
            /** Defects */
            defects?: components["schemas"]["KiuwanDefectOut"][];
            /**
             * Filename
             * @default
             */
            fileName: string;
            /** Findings */
            findings?: components["schemas"]["FindingOut"][];
            /**
             * Rows
             * @default 0
             */
            rows: number;
        };
        /**
         * LLMCallOut
         * @description Metadatos de una llamada al modelo. Sin contenido: podría llevar PHI.
         */
        LLMCallOut: {
            /** Agentid */
            agentId: string;
            /** At */
            at?: string | null;
            /**
             * Attempts
             * @default 1
             */
            attempts: number;
            /** Durationms */
            durationMs: number;
            /**
             * Error
             * @default
             */
            error: string;
            /** Model */
            model: string;
            /** Promptversion */
            promptVersion: number;
            /** Provider */
            provider: string;
            /** Toolsrejected */
            toolsRejected?: string[];
            /** Toolsused */
            toolsUsed?: string[];
            usage: components["schemas"]["UsageOut"];
        };
        /** LoginIn */
        LoginIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** ModelCatalogOut */
        ModelCatalogOut: {
            /** Providers */
            providers: {
                [key: string]: components["schemas"]["ProviderCatalogOut"];
            };
        };
        /** ModelInfoOut */
        ModelInfoOut: {
            /** Id */
            id: string;
            /** Inperm */
            inPerM: number;
            /** Label */
            label: string;
            /** Outperm */
            outPerM: number;
        };
        /**
         * PhiClassification
         * @description ¿El requerimiento puede tocar PHI? `DESCONOCIDO` se trata como `SI`.
         * @enum {string}
         */
        PhiClassification: "si" | "no" | "desconocido";
        /**
         * PhiDetectionOut
         * @description Detección de PHI: tipo, archivo y línea. **Nunca el valor.**
         */
        PhiDetectionOut: {
            /** File */
            file: string;
            /** Identifier */
            identifier: string;
            /** Line */
            line?: number | null;
            /**
             * Masked
             * @default
             */
            masked: string;
            /**
             * Url
             * @default
             */
            url: string;
            /** Where */
            where: string;
        };
        /** PlanItemOut */
        PlanItemOut: {
            /** Agentid */
            agentId: string;
            /** Enabled */
            enabled: boolean;
            /**
             * Reason
             * @default
             */
            reason: string;
            /**
             * Source
             * @default regla
             */
            source: string;
            /** Suggested */
            suggested: boolean;
        };
        /** PlanOut */
        PlanOut: {
            /** Enabledagents */
            enabledAgents?: string[];
            /** Items */
            items: components["schemas"]["PlanItemOut"][];
            /**
             * Overriddenby
             * @default
             */
            overriddenBy: string;
            /**
             * Suggestedat
             * Format: date-time
             */
            suggestedAt: string;
        };
        /** PlanViewOut */
        PlanViewOut: {
            /** Blocked */
            blocked: boolean;
            plan: components["schemas"]["PlanOut"];
            /** Warnings */
            warnings?: components["schemas"]["PlanWarningOut"][];
        };
        /** PlanWarningOut */
        PlanWarningOut: {
            /** Agentid */
            agentId: string;
            /** Blocks */
            blocks: boolean;
            /** Level */
            level: string;
            /** Text */
            text: string;
        };
        /** PrivacyReportOut */
        PrivacyReportOut: {
            /** Detections */
            detections?: components["schemas"]["PhiDetectionOut"][];
            /** Findings */
            findings?: components["schemas"]["FindingOut"][];
            /**
             * Minimumnecessary
             * @default
             */
            minimumNecessary: string;
            /** Safeguards */
            safeguards?: components["schemas"]["SafeguardCheckOut"][];
        };
        /**
         * ProfileSnapshotOut
         * @description Lo que se congeló al arrancar la ejecución. No cambia nunca.
         */
        ProfileSnapshotOut: {
            /**
             * Maxsteps
             * @default 4
             */
            maxSteps: number;
            /** Model */
            model: string;
            /** Promptversion */
            promptVersion: number;
            /** Provider */
            provider: string;
            /**
             * Temperature
             * @default 0
             */
            temperature: number;
        };
        /** PromptVersionOut */
        PromptVersionOut: {
            /** Author */
            author: string;
            /** Note */
            note: string;
            /**
             * Savedat
             * Format: date-time
             */
            savedAt: string;
            /** Systemprompt */
            systemPrompt: string;
            /** Taskprompt */
            taskPrompt: string;
            /** Version */
            version: number;
        };
        /** ProviderCatalogOut */
        ProviderCatalogOut: {
            /** Baa */
            baa?: boolean | null;
            /** Models */
            models?: components["schemas"]["ModelInfoOut"][];
        };
        /** RepoCommitOut */
        RepoCommitOut: {
            /**
             * Author
             * @default
             */
            author: string;
            /**
             * Date
             * @default
             */
            date: string;
            /**
             * Message
             * @default
             */
            message: string;
            /** Sha */
            sha: string;
            /**
             * Url
             * @default
             */
            url: string;
        };
        /** RepoFileOut */
        RepoFileOut: {
            /**
             * Additions
             * @default 0
             */
            additions: number;
            /**
             * Deletions
             * @default 0
             */
            deletions: number;
            /**
             * Haspatch
             * @default false
             */
            hasPatch: boolean;
            /** Path */
            path: string;
            /** Status */
            status: string;
        };
        /** RepoOut */
        RepoOut: {
            /**
             * Aheadby
             * @default 0
             */
            aheadBy: number;
            /** Base */
            base: string;
            /** Branch */
            branch: string;
            /** Commits */
            commits?: components["schemas"]["RepoCommitOut"][];
            /**
             * Compareurl
             * @default
             */
            compareUrl: string;
            /** Defaultbranch */
            defaultBranch: string;
            /**
             * Description
             * @default
             */
            description: string;
            /** Fetchedat */
            fetchedAt?: string | null;
            /** Files */
            files?: components["schemas"]["RepoFileOut"][];
            /**
             * Filestruncated
             * @default false
             */
            filesTruncated: boolean;
            /** Fullname */
            fullName: string;
            /** Headsha */
            headSha: string;
            /** Htmlurl */
            htmlUrl: string;
            /** Languages */
            languages?: {
                [key: string]: number;
            };
            /** Name */
            name: string;
            /** Owner */
            owner: string;
            /** Provider */
            provider: string;
            /**
             * Rangelabel
             * @default
             */
            rangeLabel: string;
        };
        /** RequirementOut */
        RequirementOut: {
            /** Acceptancecriteria */
            acceptanceCriteria?: string[];
            /** Attachments */
            attachments?: components["schemas"]["AttachmentOut"][];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Description */
            description: string;
            /** Handlesphi */
            handlesPhi: boolean;
            /** Id */
            id: string;
            /** Owner */
            owner: string;
            /** Phi */
            phi: string;
            /**
             * Phisetby
             * @default
             */
            phiSetBy: string;
            /** Title */
            title: string;
        };
        /** RequirementPage */
        RequirementPage: {
            /** Items */
            items: components["schemas"]["RequirementSummaryOut"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /**
         * RequirementSummaryOut
         * @description Requerimiento con lo que necesita la lista: última ejecución y agentes planificados.
         */
        RequirementSummaryOut: {
            /** Acceptancecriteria */
            acceptanceCriteria?: string[];
            /** Attachments */
            attachments?: components["schemas"]["AttachmentOut"][];
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Description */
            description: string;
            /** Handlesphi */
            handlesPhi: boolean;
            /** Id */
            id: string;
            lastRun?: components["schemas"]["RunSummaryOut"] | null;
            /** Owner */
            owner: string;
            /** Phi */
            phi: string;
            /**
             * Phisetby
             * @default
             */
            phiSetBy: string;
            /** Plannedagents */
            plannedAgents?: string[];
            /** Title */
            title: string;
        };
        /**
         * Role
         * @description Roles del equipo. Se corresponden con los del prototipo (`governance.ts`).
         * @enum {string}
         */
        Role: "administrador" | "lider_tecnico" | "qa" | "desarrollador" | "arquitecto" | "analista" | "observador";
        /** RunDetailOut */
        RunDetailOut: {
            deliverables: components["schemas"]["DeliverablesOut"];
            /** Events */
            events?: components["schemas"]["TraceEventOut"][] | null;
            run: components["schemas"]["RunOut"];
        };
        /** RunOut */
        RunOut: {
            /** Cancelledat */
            cancelledAt?: string | null;
            /** Enabledagents */
            enabledAgents?: string[];
            /**
             * Error
             * @default
             */
            error: string;
            /** Executions */
            executions?: {
                [key: string]: components["schemas"]["AgentExecutionOut"];
            };
            /** Finishedat */
            finishedAt?: string | null;
            /** Id */
            id: string;
            /** Profiles */
            profiles?: {
                [key: string]: components["schemas"]["ProfileSnapshotOut"];
            };
            /** Requirementid */
            requirementId: string;
            /**
             * Startedat
             * Format: date-time
             */
            startedAt: string;
            /** Startedby */
            startedBy: string;
            /** Status */
            status: string;
            usage: components["schemas"]["UsageOut"];
        };
        /** RunPage */
        RunPage: {
            /** Items */
            items: components["schemas"]["RunOut"][];
            /** Limit */
            limit: number;
            /** Offset */
            offset: number;
            /** Total */
            total: number;
        };
        /**
         * RunSummaryOut
         * @description Resumen de una ejecución para las listas: lo justo para pintar una fila.
         */
        RunSummaryOut: {
            /**
             * Completedagents
             * @default 0
             */
            completedAgents: number;
            /** Finishedat */
            finishedAt?: string | null;
            /** Id */
            id: string;
            /**
             * Startedat
             * Format: date-time
             */
            startedAt: string;
            /** Status */
            status: string;
            /**
             * Totalagents
             * @default 0
             */
            totalAgents: number;
            /** Verdict */
            verdict?: string | null;
        };
        /** SafeguardCheckOut */
        SafeguardCheckOut: {
            /**
             * Evidence
             * @default
             */
            evidence: string;
            /** Id */
            id: string;
            /** Status */
            status: string;
        };
        /**
         * SaveSecretIn
         * @description Lo que entra. `value` es lo único que no vuelve a salir por ninguna ruta.
         */
        SaveSecretIn: {
            /** Expiresat */
            expiresAt?: string | null;
            kind: components["schemas"]["SecretKind"];
            /**
             * Name
             * @description Host, URL del sitio o proveedor
             */
            name: string;
            /**
             * Scope
             * @description Vacío = toda la organización. Si no, el requerimiento al que pertenece.
             * @default
             */
            scope: string;
            /**
             * Username
             * @description Usuario, cuando es un par usuario/contraseña
             * @default
             */
            username: string;
            /**
             * Value
             * @description El secreto. No se devuelve nunca.
             */
            value: string;
        };
        /**
         * SecretKind
         * @description Para qué sirve el secreto. Determina quién lo pide y cómo se usa.
         * @enum {string}
         */
        SecretKind: "git_token" | "site_credential" | "llm_api_key" | "azure_devops";
        /**
         * SecretOut
         * @description Un secreto, tal y como se puede enseñar.
         *
         *     **No tiene campo para el valor, y es deliberado**: se construye desde `SecretMetadata`, que
         *     tampoco lo tiene, así que ninguna ruta puede devolverlo por descuido. `hint` son los cuatro
         *     últimos caracteres, lo justo para distinguir dos tokens sin reconstruir ninguno.
         */
        SecretOut: {
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Createdby */
            createdBy: string;
            /** Expiresat */
            expiresAt?: string | null;
            /**
             * Hint
             * @default
             */
            hint: string;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Kindlabel */
            kindLabel: string;
            /** Lastusedat */
            lastUsedAt?: string | null;
            /** Name */
            name: string;
            /** Revokedat */
            revokedAt?: string | null;
            /**
             * Revokedby
             * @default
             */
            revokedBy: string;
            /** Scope */
            scope: string;
            /** Status */
            status: string;
            /**
             * Updatedat
             * Format: date-time
             */
            updatedAt: string;
            /**
             * Username
             * @default
             */
            username: string;
            /**
             * Uses
             * @default 0
             */
            uses: number;
        };
        /** SecretPage */
        SecretPage: {
            /** Items */
            items: components["schemas"]["SecretOut"][];
            /** Total */
            total: number;
        };
        /**
         * SessionOut
         * @description Quién eres y qué puedes hacer. Lo pide la aplicación al cargar.
         */
        SessionOut: {
            /**
             * Authenticated
             * @default false
             */
            authenticated: boolean;
            user?: components["schemas"]["UserOut"] | null;
        };
        /** SqlReportOut */
        SqlReportOut: {
            /**
             * Engine
             * @default
             */
            engine: string;
            /** Findings */
            findings?: components["schemas"]["FindingOut"][];
            /** Scripts */
            scripts?: components["schemas"]["SqlScriptOut"][];
        };
        /** SqlScriptOut */
        SqlScriptOut: {
            /** File */
            file: string;
            /**
             * Kind
             * @default
             */
            kind: string;
            /**
             * Statements
             * @default 0
             */
            statements: number;
        };
        /** StartRunIn */
        StartRunIn: {
            /** Enabledagents */
            enabledAgents?: components["schemas"]["AgentId"][] | null;
        };
        /** TestsReportOut */
        TestsReportOut: {
            /**
             * Command
             * @default
             */
            command: string;
            /**
             * Coverage
             * @default 0
             */
            coverage: number;
            /** Findings */
            findings?: components["schemas"]["FindingOut"][];
            /** Framework */
            framework: string;
            /** Tests */
            tests?: components["schemas"]["GeneratedTestOut"][];
        };
        /** TraceEventOut */
        TraceEventOut: {
            /** Agent */
            agent?: string | null;
            /**
             * At
             * Format: date-time
             */
            at: string;
            /** Data */
            data?: {
                [key: string]: unknown;
            };
            /**
             * Detail
             * @default
             */
            detail: string;
            /** Runid */
            runId: string;
            /** Seq */
            seq: number;
            /**
             * Title
             * @default
             */
            title: string;
            /** To */
            to?: string | null;
            /** Type */
            type: string;
            usage?: components["schemas"]["UsageOut"] | null;
        };
        /** UiScenarioOut */
        UiScenarioOut: {
            /**
             * A11Yissues
             * @default 0
             */
            a11YIssues: number;
            /**
             * Browser
             * @default
             */
            browser: string;
            /**
             * Durationms
             * @default 0
             */
            durationMs: number;
            /**
             * Failurereason
             * @default
             */
            failureReason: string;
            /** Name */
            name: string;
            /** Status */
            status: string;
            /** Steps */
            steps?: string[];
        };
        /** UiuxReportOut */
        UiuxReportOut: {
            /**
             * Baseurl
             * @default
             */
            baseUrl: string;
            /** Findings */
            findings?: components["schemas"]["FindingOut"][];
            /** Scenarios */
            scenarios?: components["schemas"]["UiScenarioOut"][];
        };
        /** UpdatePlanIn */
        UpdatePlanIn: {
            /** Enabledagents */
            enabledAgents: components["schemas"]["AgentId"][];
        };
        /** UpdateUserIn */
        UpdateUserIn: {
            /** Active */
            active?: boolean | null;
            /** Name */
            name?: string | null;
            role?: components["schemas"]["Role"] | null;
        };
        /** UsageOut */
        UsageOut: {
            /**
             * Costusd
             * @default 0
             */
            costUsd: number;
            /**
             * Tokensin
             * @default 0
             */
            tokensIn: number;
            /**
             * Tokensout
             * @default 0
             */
            tokensOut: number;
        };
        /**
         * UserOut
         * @description Una persona. **Sin contraseña ni hash**: `User` del dominio tampoco los tiene.
         */
        UserOut: {
            /** Active */
            active: boolean;
            /**
             * Createdat
             * Format: date-time
             */
            createdAt: string;
            /** Email */
            email: string;
            /** Id */
            id: string;
            /** Initials */
            initials: string;
            /** Lastloginat */
            lastLoginAt?: string | null;
            /**
             * Locked
             * @default false
             */
            locked: boolean;
            /**
             * Mustchangepassword
             * @default false
             */
            mustChangePassword: boolean;
            /** Name */
            name: string;
            /** Permissions */
            permissions: string[];
            /** Provider */
            provider: string;
            /** Role */
            role: string;
            /** Rolelabel */
            roleLabel: string;
        };
        /** UserPage */
        UserPage: {
            /** Items */
            items: components["schemas"]["UserOut"][];
            /** Total */
            total: number;
        };
        /** VerdictReportOut */
        VerdictReportOut: {
            /** Confidence */
            confidence: number;
            /** Guardrails */
            guardrails?: string[];
            /** Rationale */
            rationale: string;
            /** Verdict */
            verdict: string;
        };
        /** VtrReportOut */
        VtrReportOut: {
            /**
             * Outputname
             * @default
             */
            outputName: string;
            /** Sections */
            sections?: components["schemas"]["VtrSectionOut"][];
            /**
             * Templatename
             * @default
             */
            templateName: string;
        };
        /** VtrSectionOut */
        VtrSectionOut: {
            /**
             * Content
             * @default
             */
            content: string;
            /** Sources */
            sources?: string[];
            /** Status */
            status: string;
            /** Title */
            title: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    index_api_audit_get: {
        parameters: {
            query?: {
                /** @description Requerimiento o ejecución */
                target?: string | null;
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditPage"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    verify_api_audit_verify_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AuditVerificationOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    catalog_api_auth_catalog_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    login_api_auth_login_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    logout_api_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    me_api_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    change_password_api_auth_password_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ChangePasswordBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    agents_api_catalog_agents_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["AgentCatalogOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    models_api_catalog_models_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelCatalogOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    profiles_api_catalog_profiles_get: {
        parameters: {
            query?: {
                requirementId?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: components["schemas"]["AgentProfileOut"];
                    };
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    health_api_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    index_api_requirements_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RequirementPage"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    create_api_requirements_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateRequirementIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RequirementOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    detail_api_requirements__requirement_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RequirementOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    add_attachment_api_requirements__requirement_id__attachments_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["AttachmentIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RequirementOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    classify_phi_api_requirements__requirement_id__phi_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ClassifyPhiIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RequirementOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    get_plan_api_requirements__requirement_id__plan_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanViewOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    update_plan_api_requirements__requirement_id__plan_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdatePlanIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanViewOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    suggest_plan_api_requirements__requirement_id__plan_post: {
        parameters: {
            query?: {
                /** @description Pedir además al Orquestador que revise la propuesta */
                assisted?: boolean;
            };
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PlanViewOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    connect_repo_api_requirements__requirement_id__repo_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ConnectRepoIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RequirementOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    list_runs_api_requirements__requirement_id__runs_get: {
        parameters: {
            query?: {
                limit?: number;
                offset?: number;
            };
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunPage"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    start_run_api_requirements__requirement_id__runs_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                requirement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StartRunIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    detail_api_runs__run_id__get: {
        parameters: {
            query?: {
                /** @description Incluir la traza completa */
                events?: boolean;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunDetailOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    cancel_api_runs__run_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    deliverables_api_runs__run_id__deliverables_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DeliverablesOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    trace_api_runs__run_id__events_get: {
        parameters: {
            query?: {
                afterSeq?: number;
            };
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TraceEventOut"][];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    index_api_secrets_get: {
        parameters: {
            query?: {
                /** @description Filtrar por ámbito. Ausente = todos; vacío = organización. */
                scope?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SecretPage"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    save_api_secrets_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveSecretIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SecretOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    revoke_api_secrets__secret_id__delete: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                secret_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SecretOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    index_api_users_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserPage"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    create_api_users_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CreateUserIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
    update_api_users__user_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                user_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["UpdateUserIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Petición inválida */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Presupuesto de la ejecución agotado */
            402: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Prohibido por política (PHI, BAA, herramienta) */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description No existe */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Conflicto: el plan está bloqueado */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description La petición no tiene el formato esperado */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Error interno */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
            /** @description Fallo del proveedor de IA */
            502: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ApiError"];
                };
            };
        };
    };
}
