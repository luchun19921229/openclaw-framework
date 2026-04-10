/**
 * Agent Runtime
 *
 * The core agent lifecycle: initialization, message processing,
 * tool invocation, and session management.
 *
 * @module @openclaw/core/agent
 */

import { EventEmitter } from 'node:events';

/**
 * Agent lifecycle states.
 * @enum {string}
 */
export const AgentStatus = {
  IDLE: 'idle',
  STARTING: 'starting',
  RUNNING: 'running',
  THINKING: 'thinking',
  STOPPING: 'stopping',
  STOPPED: 'stopped',
  ERROR: 'error',
};

/**
 * Represents an AI agent with message processing, tool use, and memory.
 *
 * @fires Agent#message - Emitted when the agent produces a response
 * @fires Agent#status - Emitted when agent status changes
 * @fires Agent#error - Emitted on errors
 *
 * @example
 * const agent = new Agent({
 *   name: 'my-bot',
 *   systemPrompt: 'You are a helpful coding assistant.',
 * });
 *
 * agent.setGateway(myGateway);
 * agent.setMemory(myMemory);
 *
 * await agent.start();
 * const reply = await agent.chat('Write a hello world in Python');
 * console.log(reply);
 * await agent.stop();
 */
export class Agent extends EventEmitter {
  /** @type {string} */
  name;
  /** @type {AgentStatus} */
  status = AgentStatus.IDLE;
  /** @type {string} */
  systemPrompt;
  /** @type {Array<{role: string, content: string}>} */
  conversation = [];
  /** @type {Map<string, Function>} */
  #tools = new Map();
  /** @type {object|null} */
  #gateway = null;
  /** @type {object|null} */
  #memory = null;
  /** @type {Map<string, object>} */
  #skills = new Map();
  /** @type {string} */
  #sessionId;

  /**
   * @param {object} config
   * @param {string} [config.name='agent'] - Agent name
   * @param {string} [config.systemPrompt] - System prompt
   */
  constructor(config = {}) {
    super();
    this.name = config.name || 'agent';
    this.systemPrompt = config.systemPrompt || 'You are a helpful assistant.';
    this.#sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

    // Initialize with system message
    this.conversation = [
      { role: 'system', content: this.systemPrompt },
    ];
  }

  /** Attach an LLM gateway. */
  setGateway(gateway) {
    this.#gateway = gateway;
    return this;
  }

  /** Attach a memory manager. */
  setMemory(memory) {
    this.#memory = memory;
    return this;
  }

  /** Register a skill. */
  useSkill(skill) {
    if (skill?.name) {
      this.#skills.set(skill.name, skill);
      // Register skill-provided tools
      if (skill.tools) {
        for (const [name, handler] of Object.entries(skill.tools)) {
          this.#tools.set(name, handler);
        }
      }
      this.emit('skill:loaded', skill.name);
    }
    return this;
  }

  /** Register a custom tool directly. */
  registerTool(name, handler) {
    this.#tools.set(name, handler);
    return this;
  }

  /**
   * Start the agent. Initializes memory and transitions to RUNNING.
   */
  async start() {
    this.#setStatus(AgentStatus.STARTING);

    if (this.#memory) {
      await this.#memory.connect();
      // Restore previous conversation if available
      const history = await this.#memory.getHistory(this.#sessionId);
      if (history?.length) {
        this.conversation = [
          { role: 'system', content: this.systemPrompt },
          ...history,
        ];
      }
    }

    this.#setStatus(AgentStatus.RUNNING);
    this.emit('started', { sessionId: this.#sessionId });
  }

  /**
   * Stop the agent gracefully. Persists memory and cleans up.
   */
  async stop() {
    this.#setStatus(AgentStatus.STOPPING);

    if (this.#memory) {
      // Persist conversation history
      const history = this.conversation.filter((m) => m.role !== 'system');
      await this.#memory.saveHistory(this.#sessionId, history);
      await this.#memory.disconnect();
    }

    this.#setStatus(AgentStatus.STOPPED);
    this.emit('stopped', { sessionId: this.#sessionId });
  }

  /**
   * Send a user message and get the agent's response.
   *
   * @param {string} message - User message
   * @param {object} [options] - Options (stream, temperature, etc.)
   * @returns {Promise<string>} The agent's reply
   */
  async chat(message, options = {}) {
    if (!this.#gateway) {
      throw new Error('No gateway configured. Call agent.setGateway() first.');
    }

    // Append user message
    this.conversation.push({ role: 'user', content: message });

    // Recall relevant memories
    if (this.#memory) {
      const context = await this.#memory.recall(message, { limit: 3 });
      if (context?.length) {
        // Inject as a hidden context message
        this.conversation.splice(1, 0, {
          role: 'system',
          content: `[Relevant context]\n${context.map((c) => c.content).join('\n---\n')}`,
        });
      }
    }

    this.#setStatus(AgentStatus.THINKING);

    try {
      const response = await this.#gateway.chat(this.conversation, options);

      // Append assistant response
      this.conversation.push({
        role: 'assistant',
        content: response.content,
      });

      // Store in memory
      if (this.#memory) {
        await this.#memory.store({
          role: 'user',
          content: message,
          timestamp: Date.now(),
        });
        await this.#memory.store({
          role: 'assistant',
          content: response.content,
          timestamp: Date.now(),
        });
      }

      this.#setStatus(AgentStatus.RUNNING);
      this.emit('message', {
        role: 'assistant',
        content: response.content,
        usage: response.usage,
      });

      return response.content;
    } catch (err) {
      this.#setStatus(AgentStatus.ERROR);
      this.emit('error', err);
      throw err;
    }
  }

  /**
   * Stream a response for a user message.
   *
   * @param {string} message - User message
   * @param {object} [options]
   * @returns {AsyncGenerator<string>}
   */
  async *stream(message, options = {}) {
    if (!this.#gateway) {
      throw new Error('No gateway configured.');
    }

    this.conversation.push({ role: 'user', content: message });
    this.#setStatus(AgentStatus.THINKING);

    let fullContent = '';

    try {
      for await (const chunk of this.#gateway.stream(this.conversation, options)) {
        fullContent += chunk;
        yield chunk;
      }

      this.conversation.push({ role: 'assistant', content: fullContent });

      if (this.#memory) {
        await this.#memory.store({ role: 'user', content: message, timestamp: Date.now() });
        await this.#memory.store({ role: 'assistant', content: fullContent, timestamp: Date.now() });
      }

      this.#setStatus(AgentStatus.RUNNING);
    } catch (err) {
      this.#setStatus(AgentStatus.ERROR);
      this.emit('error', err);
      throw err;
    }
  }

  /** Get current agent state snapshot. */
  getState() {
    return {
      name: this.name,
      status: this.status,
      sessionId: this.#sessionId,
      messageCount: this.conversation.length,
      skills: [...this.#skills.keys()],
      tools: [...this.#tools.keys()],
    };
  }

  /** Reset conversation (keeps agent running). */
  reset() {
    this.conversation = [{ role: 'system', content: this.systemPrompt }];
    this.#sessionId = `session_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
    this.emit('reset', { sessionId: this.#sessionId });
  }

  // --- Private ---

  #setStatus(status) {
    const prev = this.status;
    this.status = status;
    if (prev !== status) {
      this.emit('status', { from: prev, to: status });
    }
  }
}
