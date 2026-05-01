import NextAuth from 'next-auth'
import GitHub from 'next-auth/providers/github'

export type DashboardRole =
  | 'SUPER_ADMIN'
  | 'SYSTEM_ADMIN'
  | 'CONTENT'
  | 'ANALYST'
  | 'SUPPORT'
  | 'NODE_ADMIN'

const GITHUB_ALLOWLIST: Record<string, DashboardRole> = {
  NeaBouli: 'SUPER_ADMIN',
}

export const ROLE_MODULES: Record<DashboardRole, string[]> = {
  SUPER_ADMIN: [
    'overview',
    'system',
    'bills',
    'votes',
    'cplm',
    'users',
    'logs',
  ],
  SYSTEM_ADMIN: ['overview', 'system', 'bills', 'votes', 'logs'],
  CONTENT: ['overview', 'bills', 'votes'],
  ANALYST: ['overview', 'bills', 'votes', 'cplm'],
  SUPPORT: ['overview', 'users'],
  NODE_ADMIN: ['overview', 'system', 'logs'],
}

export function canAccess(role: DashboardRole, module: string): boolean {
  return ROLE_MODULES[role]?.includes(module) ?? false
}

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.GITHUB_CLIENT_ID,
      clientSecret: process.env.GITHUB_CLIENT_SECRET,
    }),
  ],
  callbacks: {
    async signIn({ profile }) {
      const username = (profile as { login?: string })?.login
      if (!username || !(username in GITHUB_ALLOWLIST)) return false
      return true
    },
    async jwt({ token, profile }) {
      if (profile) {
        const username = (profile as { login?: string })?.login
        if (username) {
          token.githubUsername = username
          token.role = GITHUB_ALLOWLIST[username] ?? null
        }
      }
      return token
    },
    async session({ session, token }) {
      session.user = {
        ...session.user,
        githubUsername: token.githubUsername as string,
        role: token.role as DashboardRole,
      }
      return session
    },
  },
  pages: {
    signIn: '/login',
  },
})

declare module 'next-auth' {
  interface Session {
    user: {
      name?: string | null
      email?: string | null
      image?: string | null
      githubUsername: string
      role: DashboardRole
    }
  }
}
