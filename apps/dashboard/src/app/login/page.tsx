'use client'

import { signIn } from 'next-auth/react'

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="bg-white border border-gray-200 rounded-2xl shadow-sm p-8 text-center">
          {/* Logo */}
          <div className="mb-6">
            <div className="text-3xl font-bold text-blue-600 tracking-tight">
              ekklesia.gr
            </div>
            <div
              className="text-sm text-gray-500 mt-1 font-medium"
              data-en="Admin Dashboard"
            >
              Πίνακας Διαχείρισης
            </div>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-100 my-6" />

          {/* Description */}
          <p
            className="text-sm text-gray-600 mb-6"
            data-en="Access restricted to authorized administrators only."
          >
            Πρόσβαση αποκλειστικά για εξουσιοδοτημένους διαχειριστές.
          </p>

          {/* GitHub Sign In Button */}
          <button
            onClick={() => signIn('github', { callbackUrl: '/' })}
            className="w-full flex items-center justify-center gap-3 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 text-white font-medium py-3 px-4 rounded-lg transition-colors text-sm"
            data-en="Sign in with GitHub"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="currentColor"
              className="w-5 h-5"
            >
              <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z" />
            </svg>
            Σύνδεση με GitHub
          </button>

          {/* Footer */}
          <p className="text-xs text-gray-400 mt-6">
            © 2026 V-Labs Development · ekklesia.gr
          </p>
        </div>
      </div>
    </div>
  )
}
