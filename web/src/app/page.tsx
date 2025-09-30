"use client"

import { useEffect } from "react"
import { useRouter } from "next/navigation"

export default function HomePage() {
    const router = useRouter()

    useEffect(() => {
        // Check if user has credentials, if so redirect to dashboard
        try {
            const apiKeyId = localStorage.getItem("composer_api_key_id")
            const apiSecret = localStorage.getItem("composer_api_secret")

            if (apiKeyId && apiSecret) {
                router.replace("/dashboard")
            } else {
                router.replace("/login")
            }
        } catch {
            router.replace("/login")
        }
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