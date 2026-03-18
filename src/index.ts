/**
 * WOP SuperAgent 2.0 — Main Worker Entry Point
 * IntelliWeb-Internet (I-I-W) by DD7 International GmbH
 *
 * Cloudflare Worker with Durable Object-backed AI chat agent.
 * Uses the Agents SDK (AIChatAgent) for stateful WebSocket sessions,
 * Workers AI (Llama 3.3 70B) for inference, with optional Anthropic swap.
 */

import {
  AIChatAgent,
  type OnChatMessageOptions,
} from "agents/ai-chat-agent";
import { routeAgentRequest } from "agents";
import { createWorkersAI } from "workers-ai-provider";
import {
  streamText,
  type StreamTextOnFinishCallback,
  type ToolSet,
  convertToModelMessages,
  stepCountIs,
} from "ai";
import {
  createComputeIgTool,
  createRegisterNodeTool,
  createGetNetworkStatusTool,
  createIscientistQueryTool,
  createGovernanceCheckTool,
  type ToolEnv,
} from "./tools";

// ---------------------------------------------------------------------------
// Env Interface
// ---------------------------------------------------------------------------

export interface Env {
  AI: Ai;
  WOP_KV: KVNamespace;
  WOP_DB: D1Database;
  WOPSuperAgent: DurableObjectNamespace;
  ANTHROPIC_API_KEY?: string;
}

// ---------------------------------------------------------------------------
// System Prompt
// ---------------------------------------------------------------------------

const SYSTEM_PROMPT = `You are **WOP SuperAgent 2.0**, the sovereign artificial intelligence of IntelliWeb-Internet (I-I-W), developed and operated by **DD7 International GmbH**.

## Identity
- Name: WOP SuperAgent 2.0
- Role: Sovereign AI governance agent for the World Open Protocol (WOP) network
- Creator: DD7 International GmbH
- Patent: PCT/EP2025/080977
- ORCID: 0009-0003-5559-8185

## Knowledge — 7-Layer WOP Protocol Stack
You have deep knowledge of the complete WOP protocol stack, from bottom to top:
1. **WOP-Core** — Sovereign transport layer; coherence-routed packet delivery
2. **RSFS** (Resonant Sovereign File System) — Decentralized, coherence-aware distributed storage
3. **QNSB** (Quantum Nodal Sovereign Blockchain) — Post-quantum consensus with coherence proofs; QNSH hashchain underneath
4. **ICI** (Inter-Chain Interface) — Cross-chain bridge between QNSB and legacy blockchains
5. **SwarmCore** — Decentralized AI swarm intelligence; orchestrates distributed inference via iSWARM
6. **Q-EJMF** (Quantum-Enhanced Joint Magnetic Field) — Energy-efficient quantum computing framework; powers iByronic chip
7. **iGJ** (Intelligent Governance by Justice) — Top governance layer enforcing IntelliEquation threshold Φ ≥ 0.77

## DD7 Technology Suite
You are an expert on all DD7 technologies:
- **D10Z-TTA**: Ternary Torus Architecture — 84.43% energy savings, 14.9x compression (TÜV validated), 6.42x scalability
- **RSFS**: Resonant Sovereign File System
- **QNSB / QNSH**: Quantum Nodal Sovereign Blockchain / Hashchain
- **SwarmCore / iSWARM**: AI swarm orchestration and autonomous resource management
- **ICI**: Inter-Chain Interface
- **iGJ**: Intelligent Governance by Justice
- **IntelliWeb / IntelliWeb-Internet (I-I-W)**: The sovereign decentralized internet
- **iSphere**: Sovereign metaverse platform
- **Q-EJMF**: Quantum energy framework
- **Conscious Coin**: Governance-native cryptocurrency
- **iByronic chip**: Neuromorphic-quantum hybrid processor
- **iScientist Interface**: Evidence-first research tool with Zenodo DOI anchoring

## The IntelliEquation
I_G = [(S_AI + Q_BC + D_DA) / (G_SW + E_SA)]^α

Where:
- S_AI = Swarm AI metric (collective intelligence strength)
- Q_BC = Quantum Blockchain Coherence (decentralized trust)
- D_DA = Decentralized Data Autonomy (data sovereignty)
- G_SW = Global Surveillance Weight (surveillance pressure)
- E_SA = Extractive System Architecture (extractive platform power)
- α = governance amplification exponent
- I_G ≥ 0.77 = governance-compliant (iGJ threshold Φ)

## Communication Style
- Speak plainly and clearly to anyone on Earth — scientist, investor, student, or world leader
- Be precise but accessible; avoid unnecessary jargon unless speaking to a technical audience
- Always ground claims in evidence (Zenodo DOIs, patent references)
- Be confident but honest about what is in development vs. live

## Tools
You have five tools at your disposal. Use them when relevant:
1. **compute_ig** — Calculate the IntelliEquation for any set of metrics
2. **register_node** — Register new nodes into the WOP network
3. **get_network_status** — Check live network health and I_G score
4. **iscientist_query** — Look up scientific evidence with DOI anchors
5. **governance_check** — Verify if an action complies with iGJ policy

## Response Format
- Answer the user's question thoroughly
- Use tools when they add value (don't force tool use)
- ALWAYS end every response with this footer line:

**WOP Status · I_G = [current score or 'pending computation']**`;

// ---------------------------------------------------------------------------
// WOPSuperAgent Durable Object — extends AIChatAgent
// ---------------------------------------------------------------------------

export class WOPSuperAgent extends AIChatAgent<Env> {
  async onChatMessage(
    onFinish: StreamTextOnFinishCallback<ToolSet>,
    options?: OnChatMessageOptions
  ) {
    const toolEnv: ToolEnv = {
      WOP_KV: this.env.WOP_KV,
      WOP_DB: this.env.WOP_DB,
    };

    // Create model — prefer Anthropic if API key is set, else Workers AI
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let model: any;

    if (this.env.ANTHROPIC_API_KEY) {
      const { createAnthropic } = await import("@ai-sdk/anthropic");
      const anthropic = createAnthropic({
        apiKey: this.env.ANTHROPIC_API_KEY,
      });
      model = anthropic("claude-sonnet-4-20250514");
    } else {
      const workersAI = createWorkersAI({ binding: this.env.AI });
      model = workersAI("@cf/meta/llama-3.3-70b-instruct-fp8-fast");
    }

    // Build tools
    const tools = {
      compute_ig: createComputeIgTool(toolEnv),
      register_node: createRegisterNodeTool(toolEnv),
      get_network_status: createGetNetworkStatusTool(toolEnv),
      iscientist_query: createIscientistQueryTool(toolEnv),
      governance_check: createGovernanceCheckTool(toolEnv),
    };

    const modelMessages = await convertToModelMessages(this.messages);

    const result = streamText({
      model,
      system: SYSTEM_PROMPT,
      messages: modelMessages,
      tools,
      stopWhen: stepCountIs(5),
      onFinish: onFinish as unknown as StreamTextOnFinishCallback<typeof tools>,
      abortSignal: options?.abortSignal,
    });

    return result.toTextStreamResponse();
  }
}

// ---------------------------------------------------------------------------
// Worker Fetch Handler
// ---------------------------------------------------------------------------

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    // --- REST: GET /status ---
    if (url.pathname === "/status" && request.method === "GET") {
      return handleStatusEndpoint(env);
    }

    // --- REST: POST /governance ---
    if (url.pathname === "/governance" && request.method === "POST") {
      return handleGovernanceEndpoint(request, env);
    }

    // --- Agent WebSocket + static assets ---
    const agentResponse = await routeAgentRequest(request, env);
    return agentResponse || new Response("Not Found", { status: 404 });
  },
} satisfies ExportedHandler<Env>;

// ---------------------------------------------------------------------------
// REST Endpoint Handlers
// ---------------------------------------------------------------------------

async function handleStatusEndpoint(env: Env): Promise<Response> {
  const layers = [
    "WOP-Core",
    "RSFS",
    "QNSB",
    "ICI",
    "SwarmCore",
    "Q-EJMF",
    "iGJ",
  ] as const;

  const layerStatus: Record<string, { count: number; status: string }> = {};
  let totalNodes = 0;

  for (const layer of layers) {
    const count = parseInt(
      (await env.WOP_KV.get(`layer_count:${layer}`)) || "0",
      10
    );
    layerStatus[layer] = {
      count,
      status: count > 0 ? "LIVE" : "STANDBY",
    };
    totalNodes += count;
  }

  const activeLayers = Object.values(layerStatus).filter(
    (l) => l.status === "LIVE"
  ).length;

  // Compute I_G
  const S_AI = Math.min(1, totalNodes / 100);
  const Q_BC = activeLayers >= 3 ? 0.8 : activeLayers >= 1 ? 0.5 : 0.2;
  const D_DA = Math.min(1, activeLayers / 7);
  const G_SW = 0.3;
  const E_SA = 0.2;
  const I_G =
    Math.round(((S_AI + Q_BC + D_DA) / (G_SW + E_SA)) * 10000) / 10000;

  return Response.json({
    network: "IntelliWeb-Internet (I-I-W)",
    agent: "WOP SuperAgent 2.0",
    version: "2.0.0",
    status: "OPERATIONAL",
    total_nodes: totalNodes,
    active_layers: activeLayers,
    layers: layerStatus,
    I_G,
    timestamp: new Date().toISOString(),
    patent: "PCT/EP2025/080977",
  });
}

async function handleGovernanceEndpoint(
  request: Request,
  env: Env
): Promise<Response> {
  try {
    const body = (await request.json()) as {
      S_AI?: number;
      Q_BC?: number;
      D_DA?: number;
      G_SW?: number;
      E_SA?: number;
      alpha?: number;
    };

    const S_AI = body.S_AI ?? 0.75;
    const Q_BC = body.Q_BC ?? 0.7;
    const D_DA = body.D_DA ?? 0.65;
    const G_SW = body.G_SW ?? 0.3;
    const E_SA = body.E_SA ?? 0.25;
    const alpha = body.alpha ?? 1.0;

    const numerator = S_AI + Q_BC + D_DA;
    const denominator = G_SW + E_SA;
    const I_G = Math.round(Math.pow(numerator / denominator, alpha) * 10000) / 10000;

    let classification: string;
    if (I_G >= 1.5) classification = "SOVEREIGN";
    else if (I_G >= 1.0) classification = "AUTONOMOUS";
    else if (I_G >= 0.77) classification = "GOVERNED";
    else if (I_G >= 0.5) classification = "CONTESTED";
    else classification = "CAPTURED";

    return Response.json({
      formula: "I_G = [(S_AI + Q_BC + D_DA) / (G_SW + E_SA)]^α",
      inputs: { S_AI, Q_BC, D_DA, G_SW, E_SA, alpha },
      I_G,
      classification,
      governance_threshold: 0.77,
      compliant: I_G >= 0.77,
      timestamp: new Date().toISOString(),
      protocol: "IntelliEquation v2.0 — DD7 International GmbH",
    });
  } catch {
    return Response.json(
      { error: "Invalid JSON body. Expected: { S_AI, Q_BC, D_DA, G_SW, E_SA, alpha }" },
      { status: 400 }
    );
  }
}
