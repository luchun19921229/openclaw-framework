/**
 * OpenClaw Basic Agent Example
 *
 * Demonstrates how to create an agent with gateway and memory,
 * send messages, and handle responses.
 *
 * Run: node index.js
 */

import {
  createAgent,
  Agent,
  GatewayManager,
  MemoryManager,
} from '@openclaw/core';

async function main() {
  console.log('🐾 OpenClaw Basic Agent Example\n');

  // ─── 1. Create components individually ────────────────────────────────

  // Set up the LLM gateway
  const gateway = new GatewayManager({
    provider: 'openai',        // or 'anthropic', 'local', 'custom'
    model: 'gpt-4o',           // model to use
    // apiKey is auto-loaded from OPENAI_API_KEY env var
  });

  // Set up memory (session-based, in-memory for this example)
  const memory = new MemoryManager({
    type: 'session',
    backend: 'memory',
  });

  // Create the agent
  const agent = new Agent({
    name: 'example-bot',
    systemPrompt: 'You are a friendly AI assistant. Be concise and helpful.',
  });

  // Wire everything together
  agent.setGateway(gateway);
  agent.setMemory(memory);

  // Listen to events
  agent.on('status', ({ from, to }) => {
    console.log(`📊 Status: ${from} → ${to}`);
  });

  agent.on('error', (err) => {
    console.error(`❌ Agent error: ${err.message}`);
  });

  // ─── 2. Start the agent ───────────────────────────────────────────────

  await agent.start();
  console.log('Agent started!\n');

  // ─── 3. Send messages ─────────────────────────────────────────────────

  try {
    const reply1 = await agent.chat('Hello! What can you help me with?');
    console.log(`User: Hello! What can you help me with?`);
    console.log(`Agent: ${reply1}\n`);

    const reply2 = await agent.chat('Explain what an AI agent is in one sentence.');
    console.log(`User: Explain what an AI agent is in one sentence.`);
    console.log(`Agent: ${reply2}\n`);

    // ─── 4. Check agent state ──────────────────────────────────────────

    const state = agent.getState();
    console.log('📋 Agent state:', JSON.stringify(state, null, 2));
    console.log();

    // ─── 5. Reset and start fresh ──────────────────────────────────────

    agent.reset();
    console.log('🔄 Conversation reset.\n');

    const reply3 = await agent.chat('Tell me a joke.');
    console.log(`User: Tell me a joke.`);
    console.log(`Agent: ${reply3}\n`);

    // ─── 6. Check memory stats ─────────────────────────────────────────

    const stats = memory.getStats();
    console.log('🧠 Memory stats:', JSON.stringify(stats, null, 2));
  } catch (err) {
    console.error(`Error: ${err.message}`);
    console.log('\n💡 Make sure OPENAI_API_KEY is set in your environment.');
  } finally {
    // ─── 7. Graceful shutdown ───────────────────────────────────────────
    await agent.stop();
    console.log('\n👋 Agent stopped. Goodbye!');
  }
}

// ─── Alternative: use the shorthand factory ─────────────────────────────────

async function shorthandExample() {
  console.log('\n--- Factory shorthand example ---\n');

  const agent = createAgent({
    name: 'shorthand-bot',
    systemPrompt: 'You are a helpful assistant.',
    gateway: { provider: 'openai', model: 'gpt-4o' },
    memory: { type: 'session', backend: 'memory' },
  });

  await agent.start();
  const reply = await agent.chat('Say hello in 3 languages.');
  console.log(reply);
  await agent.stop();
}

// ─── Run ─────────────────────────────────────────────────────────────────────

main().catch(console.error);
