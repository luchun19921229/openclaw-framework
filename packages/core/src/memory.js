/**
 * Memory System
 *
 * Provides short-term (session) and long-term (persistent) memory
 * for agents. Supports pluggable backends (file, Redis, SQLite, etc.).
 *
 * @module @openclaw/core/memory
 */

/**
 * Memory storage types.
 * @enum {string}
 */
export const MemoryType = {
  /** In-memory only, lost on restart */
  SESSION: 'session',
  /** Persisted to disk/database */
  PERSISTENT: 'persistent',
  /** Vector-embedded for semantic recall */
  EMBEDDED: 'embedded',
};

/**
 * Manages agent memory — storing, recalling, and forgetting.
 *
 * @example
 * const memory = new MemoryManager({
 *   type: 'persistent',
 *   backend: 'file',
 *   path: './data/memory',
 * });
 *
 * await memory.connect();
 * await memory.store({ role: 'user', content: 'I like cats', timestamp: Date.now() });
 * const results = await memory.recall('pets');
 * await memory.disconnect();
 */
export class MemoryManager {
  /** @type {MemoryType} */
  type;
  /** @type {object} */
  #config;
  /** @type {Map<string, Array<object>>} */
  #sessionStore = new Map();
  /** @type {Array<object>} */
  #persistentLog = [];
  /** @type {boolean} */
  #connected = false;

  /**
   * @param {object} config
   * @param {string} [config.type='session'] - Memory type (session, persistent, embedded)
   * @param {string} [config.backend='memory'] - Storage backend (memory, file, redis, sqlite)
   * @param {string} [config.path] - Path for file-based backends
   * @param {number} [config.maxEntries=10000] - Max entries before pruning
   * @param {number} [config.ttl] - Time-to-live in ms (session only)
   */
  constructor(config = {}) {
    this.type = config.type || MemoryType.SESSION;
    this.#config = {
      backend: config.backend || 'memory',
      path: config.path || './data/memory',
      maxEntries: config.maxEntries ?? 10_000,
      ttl: config.ttl,
    };
  }

  /** Connect to the storage backend. */
  async connect() {
    if (this.#connected) return;

    switch (this.#config.backend) {
      case 'file':
        await this.#initFileBackend();
        break;
      case 'redis':
        // Placeholder: connect to Redis
        break;
      case 'sqlite':
        // Placeholder: connect to SQLite
        break;
      default:
        // In-memory — nothing to initialize
        break;
    }

    this.#connected = true;
  }

  /** Disconnect and flush. */
  async disconnect() {
    if (!this.#connected) return;

    if (this.type === MemoryType.PERSISTENT && this.#config.backend === 'file') {
      await this.#flushToFile();
    }

    this.#connected = false;
  }

  /**
   * Store a memory entry.
   *
   * @param {object} entry
   * @param {string} entry.role - Message role (user, assistant, system)
   * @param {string} entry.content - Message content
   * @param {number} [entry.timestamp] - Unix timestamp
   * @param {object} [entry.metadata] - Extra metadata
   */
  async store(entry) {
    const record = {
      id: `mem_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
      role: entry.role,
      content: entry.content,
      timestamp: entry.timestamp || Date.now(),
      metadata: entry.metadata || {},
    };

    this.#persistentLog.push(record);

    // Prune if over limit
    if (this.#persistentLog.length > this.#config.maxEntries) {
      this.#persistentLog = this.#persistentLog.slice(-this.#config.maxEntries);
    }
  }

  /**
   * Recall memories matching a query.
   * For session memory, does simple text matching.
   * For embedded memory, would use vector similarity.
   *
   * @param {string} query - Search query
   * @param {object} [options]
   * @param {number} [options.limit=5] - Max results
   * @returns {Promise<Array<object>>}
   */
  async recall(query, options = {}) {
    const limit = options.limit ?? 5;
    const lowerQuery = query.toLowerCase();

    // Simple keyword matching (production would use embeddings)
    const scored = this.#persistentLog
      .map((entry) => ({
        ...entry,
        score: this.#relevanceScore(lowerQuery, entry.content.toLowerCase()),
      }))
      .filter((e) => e.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit);

    return scored;
  }

  /**
   * Get conversation history for a session.
   *
   * @param {string} sessionId
   * @returns {Promise<Array<object>>}
   */
  async getHistory(sessionId) {
    return this.#sessionStore.get(sessionId) || [];
  }

  /**
   * Save conversation history for a session.
   *
   * @param {string} sessionId
   * @param {Array<object>} messages
   */
  async saveHistory(sessionId, messages) {
    this.#sessionStore.set(sessionId, messages);
  }

  /** Clear all memories. */
  async clear() {
    this.#sessionStore.clear();
    this.#persistentLog = [];
  }

  /** Get memory stats. */
  getStats() {
    return {
      type: this.type,
      backend: this.#config.backend,
      totalEntries: this.#persistentLog.length,
      sessions: this.#sessionStore.size,
      connected: this.#connected,
    };
  }

  // --- Private helpers ---

  #relevanceScore(query, content) {
    // Simple word overlap scoring
    const queryWords = query.split(/\s+/).filter(Boolean);
    const contentWords = content.split(/\s+/).filter(Boolean);
    let matches = 0;
    for (const word of queryWords) {
      if (contentWords.some((cw) => cw.includes(word) || word.includes(cw))) {
        matches++;
      }
    }
    return matches / queryWords.length;
  }

  async #initFileBackend() {
    // In production, create directory and load existing data
    // For skeleton, this is a placeholder
  }

  async #flushToFile() {
    // In production, serialize #persistentLog to disk
  }
}
