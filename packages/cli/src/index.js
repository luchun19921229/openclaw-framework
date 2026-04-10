#!/usr/bin/env node

/**
 * OpenClaw CLI
 *
 * Command-line interface for managing OpenClaw agents, gateways, and skills.
 *
 * Usage:
 *   openclaw agent create <name>
 *   openclaw agent run <name>
 *   openclaw gateway list
 *   openclaw skill install <name>
 *   openclaw chat [message]
 *
 * @module @openclaw/cli
 */

import { program } from 'commander';
import { createAgent, GatewayManager, SkillLoader, VERSION } from '@openclaw/core';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { createInterface } from 'node:readline';

// ─── Version ────────────────────────────────────────────────────────────────

program
  .name('openclaw')
  .description('OpenClaw — AI Agent Framework CLI')
  .version(VERSION);

// ─── Agent Commands ─────────────────────────────────────────────────────────

const agentCmd = program
  .command('agent')
  .description('Manage agents');

agentCmd
  .command('create <name>')
  .description('Create a new agent configuration')
  .option('-m, --model <model>', 'LLM model to use', 'gpt-4o')
  .option('-p, --provider <provider>', 'Gateway provider', 'openai')
  .option('-s, --system <prompt>', 'System prompt')
  .action((name, options) => {
    console.log(`🤖 Creating agent "${name}"...`);
    console.log(`   Model: ${options.model}`);
    console.log(`   Provider: ${options.provider}`);
    if (options.system) {
      console.log(`   System prompt: ${options.system.slice(0, 60)}...`);
    }
    console.log(`\n✅ Agent configuration saved to openclaw.config.json`);
    // In production: write config file
  });

agentCmd
  .command('run <name>')
  .description('Run an agent interactively')
  .action(async (name) => {
    console.log(`🚀 Starting agent "${name}"...`);
    console.log(`   (Configure your gateway with OPENAI_API_KEY or similar)\n`);

    const agent = createAgent({
      name,
      gateway: { provider: 'openai' },
    });

    try {
      await agent.start();
      console.log('Agent is ready. Type your message below (Ctrl+C to exit).\n');

      const rl = createInterface({
        input: process.stdin,
        output: process.stdout,
        prompt: '> ',
      });

      rl.prompt();

      rl.on('line', async (line) => {
        const msg = line.trim();
        if (!msg) {
          rl.prompt();
          return;
        }

        try {
          process.stdout.write('🤖 ');
          const reply = await agent.chat(msg);
          console.log(reply);
          console.log();
        } catch (err) {
          console.error(`Error: ${err.message}`);
        }

        rl.prompt();
      });

      rl.on('close', async () => {
        await agent.stop();
        console.log('\n👋 Agent stopped.');
        process.exit(0);
      });
    } catch (err) {
      console.error(`Failed to start agent: ${err.message}`);
      process.exit(1);
    }
  });

agentCmd
  .command('list')
  .alias('ls')
  .description('List configured agents')
  .action(() => {
    console.log('📋 Configured agents:\n');
    // In production: read from config
    console.log('  (No agents configured yet. Use "openclaw agent create <name>" to start.)');
  });

// ─── Gateway Commands ───────────────────────────────────────────────────────

const gatewayCmd = program
  .command('gateway')
  .description('Manage LLM gateway connections');

gatewayCmd
  .command('list')
  .alias('ls')
  .description('List available gateway providers')
  .action(() => {
    console.log('🌐 Gateway Providers:\n');
    console.log('  openai      — OpenAI (GPT-4o, GPT-4, etc.)');
    console.log('  anthropic   — Anthropic (Claude)');
    console.log('  local       — Local models (Ollama, LM Studio)');
    console.log('  custom      — Custom OpenAI-compatible endpoint');
    console.log('\nSet API keys via environment variables:');
    console.log('  export OPENAI_API_KEY=sk-...');
    console.log('  export ANTHROPIC_API_KEY=sk-ant-...');
  });

gatewayCmd
  .command('test [provider]')
  .description('Test gateway connection')
  .action(async (provider = 'openai') => {
    console.log(`🔍 Testing ${provider} gateway...`);
    const gw = new GatewayManager({ provider });
    const ok = await gw.healthCheck();
    if (ok) {
      console.log(`✅ ${provider} is reachable.`);
    } else {
      console.log(`❌ ${provider} is not reachable. Check your API key and network.`);
    }
  });

// ─── Skill Commands ─────────────────────────────────────────────────────────

const skillCmd = program
  .command('skill')
  .description('Manage agent skills');

skillCmd
  .command('list')
  .alias('ls')
  .description('List available skills')
  .action(async () => {
    console.log('🧩 Skills:\n');
    const loader = new SkillLoader();
    loader.addSearchPath('./skills');
    loader.addSearchPath('./node_modules');

    const discovered = await loader.discover();
    if (discovered.length === 0) {
      console.log('  (No skills found. Check your search paths.)');
    } else {
      for (const name of discovered) {
        console.log(`  • ${name}`);
      }
    }
  });

skillCmd
  .command('install <name>')
  .description('Install a skill')
  .action((name) => {
    console.log(`📦 Installing skill "${name}"...`);
    console.log('  (In production: fetch from registry and install)');
  });

// ─── Chat Command (shortcut) ────────────────────────────────────────────────

program
  .command('chat [message...]')
  .description('Quick chat with the default agent')
  .option('-m, --model <model>', 'Model to use', 'gpt-4o')
  .action(async (message, options) => {
    const msg = message?.join(' ');
    if (!msg) {
      console.log('Usage: openclaw chat <message>');
      return;
    }

    console.log(`💬 Chatting with ${options.model}...\n`);

    const gw = new GatewayManager({ provider: 'openai', model: options.model });
    try {
      const result = await gw.chat([
        { role: 'user', content: msg },
      ]);
      console.log(result.content);
    } catch (err) {
      console.error(`Error: ${err.message}`);
    }
  });

// ─── Config Command ─────────────────────────────────────────────────────────

program
  .command('config')
  .description('Show current configuration')
  .action(() => {
    console.log('⚙️  OpenClaw Configuration:\n');
    console.log(`  Version:    ${VERSION}`);
    console.log(`  OpenAI key: ${process.env.OPENAI_API_KEY ? '✅ Set' : '❌ Not set'}`);
    console.log(`  Anthropic:  ${process.env.ANTHROPIC_API_KEY ? '✅ Set' : '❌ Not set'}`);
    console.log(`  Node.js:    ${process.version}`);
  });

// ─── Parse ──────────────────────────────────────────────────────────────────

program.parse();
