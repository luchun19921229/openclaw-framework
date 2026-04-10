/**
 * Gateway Manager
 *
 * Abstracts LLM provider connections. Handles API calls, retries,
 * rate limiting, and model selection across providers.
 *
 * @module @openclaw/core/gateway
 */

/**
 * Supported gateway providers.
 * @enum {string}
 */
export const GatewayProvider = {
  OPENAI: 'openai',
  ANTHROPIC: 'anthropic',
  LOCAL: 'local',        // Ollama, LM Studio, etc.
  CUSTOM: 'custom',
};

/**
 * Manages connections to LLM providers.
 *
 * @example
 * const gw = new GatewayManager({
 *   provider: 'openai',
 *   model: 'gpt-4o',
 *   apiKey: process.env.OPENAI_API_KEY,
 * });
 *
 * const reply = await gw.chat([
 *   { role: 'system', content: 'You are helpful.' },
 *   { role: 'user', content: 'Hello!' },
 * ]);
 */
export class GatewayManager {
  /** @type {string} */
  provider;
  /** @type {string} */
  model;
  /** @type {string|null} */
  apiKey;
  /** @type {string|null} */
  baseUrl;
  /** @type {object} */
  #options;

  /**
   * @param {object} config
   * @param {string} config.provider - Provider name (openai, anthropic, local, custom)
   * @param {string} [config.model] - Model identifier
   * @param {string} [config.apiKey] - API key (reads from env if omitted)
   * @param {string} [config.baseUrl] - Custom API base URL
   * @param {number} [config.maxRetries=3] - Max retry attempts
   * @param {number} [config.timeout=60000] - Request timeout in ms
   */
  constructor(config = {}) {
    this.provider = config.provider || GatewayProvider.OPENAI;
    this.model = config.model || this.#defaultModel(this.provider);
    this.apiKey = config.apiKey || this.#loadApiKey(this.provider);
    this.baseUrl = config.baseUrl || this.#defaultBaseUrl(this.provider);
    this.#options = {
      maxRetries: config.maxRetries ?? 3,
      timeout: config.timeout ?? 60_000,
    };
  }

  /**
   * Send a chat completion request to the LLM.
   *
   * @param {Array<{role: string, content: string}>} messages - Conversation messages
   * @param {object} [options] - Override options (temperature, maxTokens, etc.)
   * @returns {Promise<{role: string, content: string, usage: object}>}
   */
  async chat(messages, options = {}) {
    const body = {
      model: this.model,
      messages,
      temperature: options.temperature ?? 0.7,
      max_tokens: options.maxTokens ?? 4096,
      ...options.extra,
    };

    const url = `${this.baseUrl}/chat/completions`;
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.apiKey}`,
    };

    let lastError;
    for (let attempt = 0; attempt < this.#options.maxRetries; attempt++) {
      try {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), this.#options.timeout);

        const res = await fetch(url, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        clearTimeout(timer);

        if (!res.ok) {
          const errorBody = await res.text();
          throw new GatewayError(`HTTP ${res.status}: ${errorBody}`, res.status);
        }

        const data = await res.json();
        const choice = data.choices?.[0];

        return {
          role: choice?.message?.role || 'assistant',
          content: choice?.message?.content || '',
          usage: data.usage || {},
          raw: data,
        };
      } catch (err) {
        lastError = err;
        if (err.name === 'AbortError') {
          throw new GatewayError('Request timed out', 408);
        }
        // Exponential backoff for retries
        if (attempt < this.#options.maxRetries - 1) {
          await new Promise((r) => setTimeout(r, 1000 * Math.pow(2, attempt)));
        }
      }
    }

    throw lastError;
  }

  /**
   * Stream a chat completion (yields chunks).
   *
   * @param {Array<{role: string, content: string}>} messages
   * @param {object} [options]
   * @returns {AsyncGenerator<string>}
   */
  async *stream(messages, options = {}) {
    const body = {
      model: this.model,
      messages,
      stream: true,
      temperature: options.temperature ?? 0.7,
      max_tokens: options.maxTokens ?? 4096,
    };

    const res = await fetch(`${this.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.apiKey}`,
      },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      throw new GatewayError(`Stream failed: HTTP ${res.status}`, res.status);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const trimmed = line.trim();
        if (!trimmed || !trimmed.startsWith('data: ')) continue;
        const payload = trimmed.slice(6);
        if (payload === '[DONE]') return;

        try {
          const parsed = JSON.parse(payload);
          const delta = parsed.choices?.[0]?.delta?.content;
          if (delta) yield delta;
        } catch {
          // Skip malformed chunks
        }
      }
    }
  }

  /** Check if the gateway is reachable. */
  async healthCheck() {
    try {
      const res = await fetch(`${this.baseUrl}/models`, {
        headers: { 'Authorization': `Bearer ${this.apiKey}` },
        signal: AbortSignal.timeout(5000),
      });
      return res.ok;
    } catch {
      return false;
    }
  }

  // --- Private helpers ---

  #defaultModel(provider) {
    const defaults = {
      [GatewayProvider.OPENAI]: 'gpt-4o',
      [GatewayProvider.ANTHROPIC]: 'claude-sonnet-4-20250514',
      [GatewayProvider.LOCAL]: 'llama3',
      [GatewayProvider.CUSTOM]: 'default',
    };
    return defaults[provider] || 'gpt-4o';
  }

  #defaultBaseUrl(provider) {
    const urls = {
      [GatewayProvider.OPENAI]: 'https://api.openai.com/v1',
      [GatewayProvider.ANTHROPIC]: 'https://api.anthropic.com/v1',
      [GatewayProvider.LOCAL]: 'http://localhost:11434/v1',
      [GatewayProvider.CUSTOM]: 'http://localhost:8080/v1',
    };
    return urls[provider] || urls[GatewayProvider.OPENAI];
  }

  #loadApiKey(provider) {
    const envKeys = {
      [GatewayProvider.OPENAI]: 'OPENAI_API_KEY',
      [GatewayProvider.ANTHROPIC]: 'ANTHROPIC_API_KEY',
    };
    const envVar = envKeys[provider];
    return envVar ? process.env[envVar] || null : null;
  }
}

/**
 * Custom error class for gateway-related errors.
 */
export class GatewayError extends Error {
  /** @type {number} */
  statusCode;

  constructor(message, statusCode = 500) {
    super(message);
    this.name = 'GatewayError';
    this.statusCode = statusCode;
  }
}
