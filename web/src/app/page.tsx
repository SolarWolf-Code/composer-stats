"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function HomePage() {
    const router = useRouter()

    useEffect(() => {
        // Check if user has active session
        async function checkSession() {
            try {
                const response = await fetch("/api/auth/session")
                if (response.ok) {
                    router.replace("/dashboard")
                } else {
                    router.replace("/login")
                }
            } catch {
                router.replace("/login")
            }
        }

        checkSession()
    }, [router])

    return (
        <div style={{
            minHeight: '100vh',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: '#0a0e1a',
            color: '#e1e5e9'
        }}>
            <div>Loading...</div>
        </div>
    )
}