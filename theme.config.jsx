import React from 'react'

const config = {
  logo: <span style={{ fontWeight: 700, fontSize: 18 }}>OpenClaw</span>,
  project: {
    link: 'https://github.com/luchun19921229/openclaw',
  },
  chat: {
    link: 'https://discord.gg/clawd',
  },
  docsRepositoryBase: 'https://github.com/luchun19921229/openclaw/tree/main/docs',
  head: (
    <>
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <meta property="og:title" content="OpenClaw" />
      <meta property="og:description" content="AI Agent Control Center - Unified workspace for managing AI agents, memory, skills, and multi-model orchestration" />
      <link rel="icon" href="/favicon.ico" />
    </>
  ),
  footer: {
    text: 'OpenClaw © 2026',
  },
  primaryHue: 220,
  primarySaturation: 10,
  sidebar: {
    defaultMenuCollapseLevel: 1,
  },
  toc: {
    backToTop: true,
  },
}

export default config
