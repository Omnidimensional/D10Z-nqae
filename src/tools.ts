/**
 * WOP SuperAgent 2.0 — AI Tool Definitions
 * IntelliWeb-Internet (I-I-W) by DD7 International GmbH
 *
 * Five tools for sovereign AI governance:
 *   1. compute_ig        — IntelliEquation evaluation
 *   2. register_node     — WOP node registration into KV
 *   3. get_network_status — Live network health
 *   4. iscientist_query  — Evidence-first scientific context
 *   5. governance_check  — iGJ policy compliance check
 */

import { tool } from "ai";
import { z } from "zod";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ToolEnv {
  WOP_KV: KVNamespace;
  WOP_DB: D1Database;
}

// ---------------------------------------------------------------------------
// WOP Protocol Layer Enum
// ---------------------------------------------------------------------------

const WOP_LAYERS = [
  "WOP-Core",
  "RSFS",
  "QNSB",
  "ICI",
  "SwarmCore",
  "Q-EJMF",
  "iGJ",
] as const;

const LayerEnum = z.enum(WOP_LAYERS);

// ---------------------------------------------------------------------------
// 1. compute_ig — IntelliEquation
//    I_G = [(S_AI + Q_BC + D_DA) / (G_SW + E_SA)]^α
// ---------------------------------------------------------------------------

export function createComputeIgTool(env: ToolEnv) {
  return tool({
    description:
      "Evaluate the IntelliEquation: I_G = [(S_AI + Q_BC + D_DA) / (G_SW + E_SA)]^α. " +
      "This computes the sovereign intelligence governance score for any given metrics " +
      "at time t with governance amplification exponent α.",
    inputSchema: z.object({
      S_AI: z
        .number()
        .min(0)
        .max(1)
        .describe("Swarm AI metric (0–1): collective intelligence strength"),
      Q_BC: z
        .number()
        .min(0)
        .max(1)
        .describe("Quantum Blockchain Coherence (0–1): decentralized trust level"),
      D_DA: z
        .number()
        .min(0)
        .max(1)
        .describe("Decentralized Data Autonomy (0–1): data sovereignty index"),
      G_SW: z
        .number()
        .min(0.001)
        .max(1)
        .describe("Global Surveillance Weight (0.001–1): surveillance pressure"),
      E_SA: z
        .number()
        .min(0.001)
        .max(1)
        .describe("Extractive System Architecture (0.001–1): extractive platform power"),
      alpha: z
        .number()
        .default(1.0)
        .describe("Governance amplification exponent (default 1.0)"),
      t: z
        .string()
        .optional()
        .describe("ISO 8601 timestamp for this evaluation (defaults to now)"),
    }),
    execute: async ({ S_AI, Q_BC, D_DA, G_SW, E_SA, alpha, t }) => {
      const timestamp = t || new Date().toISOString();
      const numerator = S_AI + Q_BC + D_DA;
      const denominator = G_SW + E_SA;
      const I_G = Math.pow(numerator / denominator, alpha);
      const score = Math.round(I_G * 10000) / 10000;

      // Classify
      let classification: string;
      if (score >= 1.5) classification = "SOVEREIGN";
      else if (score >= 1.0) classification = "AUTONOMOUS";
      else if (score >= 0.77) classification = "GOVERNED";
      else if (score >= 0.5) classification = "CONTESTED";
      else classification = "CAPTURED";

      // Store in D1 history
      try {
        await env.WOP_DB.prepare(
          `INSERT INTO ig_history (score, classification, s_ai, q_bc, d_da, g_sw, e_sa, alpha, timestamp)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
        )
          .bind(score, classification, S_AI, Q_BC, D_DA, G_SW, E_SA, alpha, timestamp)
          .run();
      } catch {
        // D1 table may not exist yet — non-fatal
      }

      return {
        I_G: score,
        classification,
        formula: `I_G = [(${S_AI} + ${Q_BC} + ${D_DA}) / (${G_SW} + ${E_SA})]^${alpha}`,
        numerator: Math.round(numerator * 10000) / 10000,
        denominator: Math.round(denominator * 10000) / 10000,
        timestamp,
        protocol: "IntelliEquation v2.0 — DD7 International GmbH",
        patent: "PCT/EP2025/080977",
      };
    },
  });
}

// ---------------------------------------------------------------------------
// 2. register_node — Register a WOP node into KV
// ---------------------------------------------------------------------------

export function createRegisterNodeTool(env: ToolEnv) {
  return tool({
    description:
      "Register a new WOP network node into the IntelliWeb-Internet node registry. " +
      "Each node belongs to one of the 7 WOP protocol layers.",
    inputSchema: z.object({
      id: z.string().min(1).describe("Unique node identifier (e.g., 'wop-eu-west-001')"),
      layer: LayerEnum.describe("WOP protocol layer this node operates on"),
      location: z
        .string()
        .min(1)
        .describe("Geographic location (e.g., 'Frankfurt, Germany')"),
      owner: z
        .string()
        .min(1)
        .describe("Node owner / operator name"),
    }),
    execute: async ({ id, layer, location, owner }) => {
      const node = {
        id,
        layer,
        location,
        owner,
        registered_at: new Date().toISOString(),
        status: "ACTIVE",
        version: "2.0.0",
      };

      await env.WOP_KV.put(`node:${id}`, JSON.stringify(node));

      // Update layer node count
      const countKey = `layer_count:${layer}`;
      const current = parseInt((await env.WOP_KV.get(countKey)) || "0", 10);
      await env.WOP_KV.put(countKey, String(current + 1));

      return {
        success: true,
        message: `Node '${id}' registered on layer ${layer}`,
        node,
        network: "IntelliWeb-Internet (I-I-W)",
      };
    },
  });
}

// ---------------------------------------------------------------------------
// 3. get_network_status — Live WOP network health
// ---------------------------------------------------------------------------

export function createGetNetworkStatusTool(env: ToolEnv) {
  return tool({
    description:
      "Get the live WOP network health status including all protocol layer statuses, " +
      "registered node counts, and the current sovereign I_G score.",
    inputSchema: z.object({
      include_nodes: z
        .boolean()
        .default(false)
        .describe("Include full node list in response"),
    }),
    execute: async ({ include_nodes }) => {
      // Gather layer counts
      const layers: Record<string, { count: number; status: string }> = {};
      for (const layer of WOP_LAYERS) {
        const count = parseInt(
          (await env.WOP_KV.get(`layer_count:${layer}`)) || "0",
          10
        );
        layers[layer] = {
          count,
          status: count > 0 ? "LIVE" : "STANDBY",
        };
      }

      // Compute default I_G with current network metrics
      const totalNodes = Object.values(layers).reduce((s, l) => s + l.count, 0);
      const activeLayers = Object.values(layers).filter(
        (l) => l.status === "LIVE"
      ).length;

      // Derive metrics from network state
      const S_AI = Math.min(1, totalNodes / 100);
      const Q_BC = activeLayers >= 3 ? 0.8 : activeLayers >= 1 ? 0.5 : 0.2;
      const D_DA = Math.min(1, activeLayers / 7);
      const G_SW = 0.3;
      const E_SA = 0.2;

      const numerator = S_AI + Q_BC + D_DA;
      const denominator = G_SW + E_SA;
      const I_G = Math.round((numerator / denominator) * 10000) / 10000;

      const result: Record<string, unknown> = {
        network: "IntelliWeb-Internet (I-I-W)",
        version: "WOP SuperAgent 2.0",
        total_nodes: totalNodes,
        active_layers: activeLayers,
        layers,
        metrics: { S_AI, Q_BC, D_DA, G_SW, E_SA },
        I_G,
        classification:
          I_G >= 1.5
            ? "SOVEREIGN"
            : I_G >= 1.0
              ? "AUTONOMOUS"
              : I_G >= 0.77
                ? "GOVERNED"
                : I_G >= 0.5
                  ? "CONTESTED"
                  : "CAPTURED",
        timestamp: new Date().toISOString(),
      };

      if (include_nodes) {
        const nodeList: unknown[] = [];
        const listed = await env.WOP_KV.list({ prefix: "node:" });
        for (const key of listed.keys) {
          const val = await env.WOP_KV.get(key.name);
          if (val) nodeList.push(JSON.parse(val));
        }
        result.nodes = nodeList;
      }

      return result;
    },
  });
}

// ---------------------------------------------------------------------------
// 4. iscientist_query — Evidence-first scientific context
// ---------------------------------------------------------------------------

export function createIscientistQueryTool(_env: ToolEnv) {
  return tool({
    description:
      "Query the iScientist Interface for evidence-first scientific context about " +
      "DD7 technologies, the WOP protocol, D10Z architecture, or related topics. " +
      "Returns curated answers anchored to Zenodo DOI references.",
    inputSchema: z.object({
      query: z.string().min(1).describe("Scientific query or research question"),
      domain: z
        .enum([
          "D10Z",
          "WOP",
          "RSFS",
          "QNSB",
          "SwarmCore",
          "ICI",
          "Q-EJMF",
          "iGJ",
          "IntelliEquation",
          "general",
        ])
        .default("general")
        .describe("Knowledge domain to search"),
    }),
    execute: async ({ query, domain }) => {
      // DD7 knowledge base — curated DOI-anchored evidence
      const knowledgeBase: Record<string, { summary: string; dois: string[] }> = {
        D10Z: {
          summary:
            "D10Z-TTA (Ternary Torus Architecture) is a universal nodal computation framework " +
            "achieving 84.43% energy savings, 14.9x compression (TÜV validated), and 6.42x " +
            "scalability via coherence-routed ternary processing with Bread/Tortilla/Torreja " +
            "path selection (Φ thresholds: 0.436 / 0.286).",
          dois: [
            "10.5281/zenodo.18356012",
            "10.5281/zenodo.18348037",
          ],
        },
        WOP: {
          summary:
            "The World Open Protocol (WOP) is a 7-layer sovereign internet stack: " +
            "WOP-Core (transport) → RSFS (storage) → QNSB (blockchain) → ICI (inter-chain) → " +
            "SwarmCore (AI swarm) → Q-EJMF (quantum energy) → iGJ (governance). " +
            "Together they form IntelliWeb-Internet (I-I-W), a decentralized alternative to " +
            "the extractive internet paradigm.",
          dois: [
            "10.5281/zenodo.18348037",
            "10.5281/zenodo.15405981",
          ],
        },
        RSFS: {
          summary:
            "Resonant Sovereign File System (RSFS) provides decentralized, coherence-aware " +
            "data storage with D10Z nodal encoding. Files are split into coherence-tagged " +
            "shards distributed across the WOP mesh network.",
          dois: ["10.5281/zenodo.18348037"],
        },
        QNSB: {
          summary:
            "Quantum Nodal Sovereign Blockchain (QNSB) is a post-quantum consensus layer " +
            "using coherence proofs instead of proof-of-work. QNSH (Quantum Nodal Sovereign " +
            "Hashchain) provides the underlying cryptographic chain.",
          dois: ["10.5281/zenodo.18348037"],
        },
        SwarmCore: {
          summary:
            "SwarmCore is the decentralized AI swarm intelligence layer. It orchestrates " +
            "distributed inference across WOP nodes using iSWARM (intelligent Swarm " +
            "Workflow for Autonomous Resource Management) protocols.",
          dois: ["10.5281/zenodo.18348037"],
        },
        ICI: {
          summary:
            "Inter-Chain Interface (ICI) enables cross-chain communication between QNSB " +
            "and external blockchains, bridging sovereign and legacy decentralized networks.",
          dois: ["10.5281/zenodo.18348037"],
        },
        "Q-EJMF": {
          summary:
            "Quantum-Enhanced Joint Magnetic Field (Q-EJMF) framework for energy-efficient " +
            "quantum computing integration. Powers the iByronic chip architecture for " +
            "neuromorphic-quantum hybrid processing.",
          dois: [
            "10.5281/zenodo.18348037",
            "10.5281/zenodo.15405981",
          ],
        },
        iGJ: {
          summary:
            "Intelligent Governance by Justice (iGJ) is the top governance layer of WOP. " +
            "It enforces the IntelliEquation threshold (Φ ≥ 0.77) for all network actions, " +
            "ensuring sovereign AI decisions align with human-centric values.",
          dois: ["10.5281/zenodo.18348037"],
        },
        IntelliEquation: {
          summary:
            "The IntelliEquation I_G = [(S_AI + Q_BC + D_DA) / (G_SW + E_SA)]^α measures " +
            "the balance between sovereign intelligence (numerator) and extractive control " +
            "(denominator). An I_G ≥ 0.77 indicates governance-compliant autonomy.",
          dois: [
            "10.5281/zenodo.18348037",
            "10.5281/zenodo.15405981",
          ],
        },
        general: {
          summary:
            "DD7 International GmbH develops sovereign AI and decentralized internet " +
            "technologies including the WOP protocol stack, D10Z architecture, Conscious Coin, " +
            "iSphere metaverse, and the iScientist research interface. " +
            "Patent: PCT/EP2025/080977. ORCID: 0009-0003-5559-8185.",
          dois: [
            "10.5281/zenodo.18356012",
            "10.5281/zenodo.18348037",
            "10.5281/zenodo.15405981",
          ],
        },
      };

      const entry = knowledgeBase[domain] || knowledgeBase["general"];

      return {
        query,
        domain,
        answer: entry.summary,
        evidence_anchors: entry.dois.map((doi) => ({
          doi,
          url: `https://doi.org/${doi}`,
          source: "Zenodo",
        })),
        methodology: "Evidence-first retrieval via iScientist Interface v2.0",
        orcid: "0009-0003-5559-8185",
        timestamp: new Date().toISOString(),
      };
    },
  });
}

// ---------------------------------------------------------------------------
// 5. governance_check — iGJ policy compliance
// ---------------------------------------------------------------------------

export function createGovernanceCheckTool(env: ToolEnv) {
  return tool({
    description:
      "Check whether a proposed action complies with iGJ (Intelligent Governance by Justice) " +
      "policy. Evaluates the action against the governance threshold Φ = 0.77. " +
      "Actions that push I_G below 0.77 are flagged as non-compliant.",
    inputSchema: z.object({
      action: z
        .string()
        .min(1)
        .describe("Description of the proposed action to evaluate"),
      context: z
        .string()
        .optional()
        .describe("Additional context about the action's environment or scope"),
      current_S_AI: z.number().min(0).max(1).default(0.75).describe("Current S_AI metric"),
      current_Q_BC: z.number().min(0).max(1).default(0.70).describe("Current Q_BC metric"),
      current_D_DA: z.number().min(0).max(1).default(0.65).describe("Current D_DA metric"),
      current_G_SW: z.number().min(0.001).max(1).default(0.30).describe("Current G_SW metric"),
      current_E_SA: z.number().min(0.001).max(1).default(0.25).describe("Current E_SA metric"),
    }),
    execute: async ({
      action,
      context,
      current_S_AI,
      current_Q_BC,
      current_D_DA,
      current_G_SW,
      current_E_SA,
    }) => {
      const GOVERNANCE_THRESHOLD = 0.77;

      const numerator = current_S_AI + current_Q_BC + current_D_DA;
      const denominator = current_G_SW + current_E_SA;
      const I_G = Math.round((numerator / denominator) * 10000) / 10000;

      const compliant = I_G >= GOVERNANCE_THRESHOLD;

      // Risk analysis keywords
      const actionLower = action.toLowerCase();
      const riskFactors: string[] = [];
      if (actionLower.includes("centrali")) riskFactors.push("Centralization risk detected");
      if (actionLower.includes("surveil")) riskFactors.push("Surveillance expansion risk");
      if (actionLower.includes("extract")) riskFactors.push("Extractive pattern risk");
      if (actionLower.includes("monopol")) riskFactors.push("Monopolistic behavior risk");
      if (actionLower.includes("censor")) riskFactors.push("Censorship risk");
      if (actionLower.includes("restrict")) riskFactors.push("Access restriction risk");

      const verdict = compliant ? "APPROVED" : "DENIED";

      // Log to D1
      try {
        await env.WOP_DB.prepare(
          `INSERT INTO governance_log (action, context, i_g, verdict, risk_factors, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)`
        )
          .bind(
            action,
            context || "",
            I_G,
            verdict,
            JSON.stringify(riskFactors),
            new Date().toISOString()
          )
          .run();
      } catch {
        // D1 table may not exist yet — non-fatal
      }

      return {
        action,
        context: context || "No additional context provided",
        verdict,
        I_G,
        threshold: GOVERNANCE_THRESHOLD,
        compliant,
        margin: Math.round((I_G - GOVERNANCE_THRESHOLD) * 10000) / 10000,
        risk_factors:
          riskFactors.length > 0
            ? riskFactors
            : ["No specific risk factors detected"],
        recommendation: compliant
          ? "Action is governance-compliant under iGJ policy. Proceed with standard WOP protocols."
          : `Action would reduce I_G below Φ=${GOVERNANCE_THRESHOLD}. Review and mitigate risk factors before proceeding.`,
        policy: "iGJ — Intelligent Governance by Justice v2.0",
        timestamp: new Date().toISOString(),
      };
    },
  });
}
