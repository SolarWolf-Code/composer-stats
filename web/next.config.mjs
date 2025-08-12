/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        // Default to Docker Compose service name for internal API routing.
        // Can be overridden at build time via API_INTERNAL_ORIGIN or NEXT_PUBLIC_API_URL
        const apiOrigin = process.env.API_INTERNAL_ORIGIN || process.env.NEXT_PUBLIC_API_URL || 'http://api:8000'
        const base = apiOrigin.replace(/\/$/, '')
        return [
            { source: '/api/:path*', destination: `${base}/api/:path*` },
        ]
    },
    eslint: { ignoreDuringBuilds: true },
    typescript: { ignoreBuildErrors: true },
}

export default nextConfig


