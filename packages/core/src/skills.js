/**
 * Skill System
 *
 * Skills are modular capabilities that extend agent functionality.
 * Each skill can provide tools, hooks, and configuration.
 *
 * @module @openclaw/core/skills
 */

import { readdir, readFile, stat } from 'node:fs/promises';
import { join, resolve } from 'node:path';

/**
 * A single loaded skill.
 *
 * @typedef {object} Skill
 * @property {string} name - Skill identifier
 * @property {string} [description] - Human-readable description
 * @property {string} [version] - Skill version
 * @property {object} [tools] - Tool handlers keyed by tool name
 * @property {Function} [init] - Initialization function
 * @property {Function} [destroy] - Cleanup function
 * @property {object} [config] - Skill configuration schema
 */

/**
 * Loads skills from the filesystem.
 *
 * @example
 * const loader = new SkillLoader();
 * loader.addSearchPath('./skills');
 * loader.addSearchPath('./node_modules');
 *
 * const skill = await loader.load('web-search');
 * console.log(skill.tools); // { search: Function, fetch: Function }
 */
export class SkillLoader {
  /** @type {string[]} */
  #searchPaths = [];
  /** @type {Map<string, Skill>} */
  #cache = new Map();

  /**
   * Add a directory to search for skills.
   *
   * @param {string} path - Directory path
   */
  addSearchPath(path) {
    const resolved = resolve(path);
    if (!this.#searchPaths.includes(resolved)) {
      this.#searchPaths.push(resolved);
    }
    return this;
  }

  /**
   * Load a skill by name.
   *
   * @param {string} name - Skill name
   * @returns {Promise<Skill>}
   */
  async load(name) {
    // Return cached if available
    if (this.#cache.has(name)) {
      return this.#cache.get(name);
    }

    // Search for the skill in search paths
    for (const searchPath of this.#searchPaths) {
      const skillPath = join(searchPath, name);

      try {
        const stats = await stat(skillPath);
        if (!stats.isDirectory()) continue;

        // Check for SKILL.md (documentation)
        const skillMdPath = join(skillPath, 'SKILL.md');
        let description = '';
        try {
          const md = await readFile(skillMdPath, 'utf-8');
          description = md.split('\n')[0].replace(/^#\s*/, '');
        } catch {
          // SKILL.md is optional
        }

        // Load skill module
        const modulePath = join(skillPath, 'index.js');
        let skillModule;
        try {
          skillModule = await import(modulePath);
        } catch {
          // Fallback: create a minimal skill
          skillModule = { default: { name, description } };
        }

        const skill = skillModule.default || skillModule;
        skill.name = skill.name || name;
        skill.description = skill.description || description;

        // Run init if defined
        if (typeof skill.init === 'function') {
          await skill.init();
        }

        this.#cache.set(name, skill);
        return skill;
      } catch {
        // Not found in this path, try next
        continue;
      }
    }

    throw new SkillError(`Skill not found: ${name}`);
  }

  /**
   * Unload a skill and run its cleanup.
   *
   * @param {string} name
   */
  async unload(name) {
    const skill = this.#cache.get(name);
    if (skill && typeof skill.destroy === 'function') {
      await skill.destroy();
    }
    this.#cache.delete(name);
  }

  /** List all loaded skills. */
  listLoaded() {
    return [...this.#cache.values()].map((s) => ({
      name: s.name,
      description: s.description,
      version: s.version,
      tools: s.tools ? Object.keys(s.tools) : [],
    }));
  }

  /** Discover available skills in search paths. */
  async discover() {
    const found = new Set();

    for (const searchPath of this.#searchPaths) {
      try {
        const entries = await readdir(searchPath, { withFileTypes: true });
        for (const entry of entries) {
          if (entry.isDirectory() && !entry.name.startsWith('.')) {
            found.add(entry.name);
          }
        }
      } catch {
        // Path doesn't exist or not readable
      }
    }

    return [...found];
  }
}

/**
 * Registry for managing all loaded skills and their tools.
 *
 * @example
 * const registry = new SkillRegistry(loader);
 * await registry.initialize(['web-search', 'code-exec']);
 *
 * const tool = registry.getTool('search');
 * const result = await tool({ query: 'OpenClaw' });
 */
export class SkillRegistry {
  /** @type {SkillLoader} */
  #loader;
  /** @type {Map<string, Function>} */
  #tools = new Map();
  /** @type {Map<string, Skill>} */
  #skills = new Map();

  constructor(loader) {
    this.#loader = loader || new SkillLoader();
  }

  /**
   * Initialize the registry with a list of skill names.
   *
   * @param {string[]} skillNames
   */
  async initialize(skillNames = []) {
    for (const name of skillNames) {
      try {
        const skill = await this.#loader.load(name);
        this.#skills.set(name, skill);

        // Register tools
        if (skill.tools) {
          for (const [toolName, handler] of Object.entries(skill.tools)) {
            this.#tools.set(toolName, handler);
          }
        }
      } catch (err) {
        console.warn(`Failed to load skill "${name}": ${err.message}`);
      }
    }
  }

  /**
   * Get a tool handler by name.
   *
   * @param {string} toolName
   * @returns {Function|undefined}
   */
  getTool(toolName) {
    return this.#tools.get(toolName);
  }

  /** Check if a tool is available. */
  hasTool(toolName) {
    return this.#tools.has(toolName);
  }

  /** List all registered tools. */
  listTools() {
    return [...this.#tools.entries()].map(([name, fn]) => ({
      name,
      source: this.#findToolSource(name),
    }));
  }

  /** Get a loaded skill by name. */
  getSkill(name) {
    return this.#skills.get(name);
  }

  /** List all loaded skills. */
  listSkills() {
    return [...this.#skills.values()].map((s) => ({
      name: s.name,
      description: s.description,
      version: s.version,
    }));
  }

  #findToolSource(toolName) {
    for (const [skillName, skill] of this.#skills) {
      if (skill.tools && toolName in skill.tools) {
        return skillName;
      }
    }
    return 'unknown';
  }
}

/**
 * Custom error class for skill-related errors.
 */
export class SkillError extends Error {
  constructor(message) {
    super(message);
    this.name = 'SkillError';
  }
}
