/** @type {import('next').NextConfig} */
const nextConfig = {
    // Removed rewrites - now using API route handlers for session-based auth
    eslint: { ignoreDuringBuilds: true },
    typescript: { ignoreBuildErrors: true },
}

export default nextConfig


