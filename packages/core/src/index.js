/**
 * OpenClaw Core Runtime
 *
 * The foundational layer for building AI agents. Provides agent lifecycle
 * management, gateway abstraction, pluggable memory, and a skill system.
 *
 * @module @openclaw/core
 */

export { Agent, AgentStatus } from './agent.js';
export { GatewayManager, GatewayProvider } from './gateway.js';
export { MemoryManager, MemoryType } from './memory.js';
export { SkillLoader, SkillRegistry } from './skills.js';

/**
 * Create a new OpenClaw agent with the given configuration.
 *
 * @param {object} config - Agent configuration
 * @param {string} config.name - Agent display name
 * @param {string} [config.systemPrompt] - System prompt for the LLM
 * @param {object} [config.gateway] - Gateway configuration
 * @param {object} [config.memory] - Memory configuration
 * @param {string[]} [config.skills] - List of skill names to load
 * @returns {Agent} A configured Agent instance
 *
 * @example
 * import { createAgent } from '@openclaw/core';
 *
 * const agent = createAgent({
 *   name: 'my-assistant',
 *   systemPrompt: 'You are a helpful assistant.',
 *   gateway: { provider: 'openai', model: 'gpt-4o' },
 *   memory: { type: 'persistent', backend: 'file' },
 *   skills: ['web-search', 'code-exec'],
 * });
 *
 * await agent.start();
 * const response = await agent.chat('Hello!');
 */
export function createAgent(config = {}) {
  const { name = 'agent', systemPrompt, gateway, memory, skills } = config;

  const agent = new Agent({ name, systemPrompt });

  // Wire up gateway if configured
  if (gateway) {
    const gw = new GatewayManager(gateway);
    agent.setGateway(gw);
  }

  // Wire up memory if configured
  if (memory) {
    const mem = new MemoryManager(memory);
    agent.setMemory(mem);
  }

  // Load skills if configured
  if (skills?.length) {
    const loader = new SkillLoader();
    for (const skillName of skills) {
      loader.load(skillName).then((skill) => agent.useSkill(skill));
    }
  }

  return agent;
}

// Version
export const VERSION = '1.0.0';
