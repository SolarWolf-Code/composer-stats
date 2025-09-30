"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

export default function LoginPage() {
    const router = useRouter()
    const [apiKeyId, setApiKeyId] = useState("")
    const [apiSecret, setApiSecret] = useState("")
    const [showSecret, setShowSecret] = useState(false)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        try {
            const k = localStorage.getItem("composer_api_key_id") || ""
            const s = localStorage.getItem("composer_api_secret") || ""
            setApiKeyId(k)
            setApiSecret(s)
        } catch (_) { }
    }, [])

    function onSubmit(e: React.FormEvent) {
        e.preventDefault()
        setError(null)
        try {
            if (!apiKeyId || !apiSecret) {
                setError("Please enter both API Key ID and Secret")
                return
            }
            localStorage.setItem("composer_api_key_id", apiKeyId.trim())
            localStorage.setItem("composer_api_secret", apiSecret.trim())
            router.push("/dashboard")
        } catch (err: any) {
            setError("Failed to save credentials")
        }
    }

    function onClear() {
        try {
            localStorage.removeItem("composer_api_key_id")
            localStorage.removeItem("composer_api_secret")
            setApiKeyId("")
            setApiSecret("")
            setError(null)
        } catch (_) { }
    }

    return (
        <div style={{
            minHeight: '100vh',
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '16px',
            backgroundColor: '#0a0e1a'
        }}>
            <div className="card" style={{ width: '100%', maxWidth: '400px' }}>
                <div className="card-header">
                    <h3 className="card-title">Sign in to ComposerAnalytics</h3>
                    <p style={{ fontSize: '12px', color: '#787b86', marginTop: '8px' }}>
                        Enter your API credentials. They are stored only in your browser and used per request.
                    </p>
                </div>
                <div className="card-body">
                    <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                        <div>
                            <label style={{
                                display: 'block',
                                color: '#e1e5e9',
                                fontSize: '14px',
                                marginBottom: '6px',
                                fontWeight: '500'
                            }}>
                                API Key ID
                            </label>
                            <input
                                type="text"
                                value={apiKeyId}
                                onChange={(e) => setApiKeyId(e.target.value)}
                                placeholder="ck_..."
                                required
                                autoFocus
                                style={{
                                    width: '100%',
                                    padding: '8px 12px',
                                    backgroundColor: '#1e222d',
                                    border: '1px solid #363a45',
                                    borderRadius: '4px',
                                    color: '#e1e5e9',
                                    fontSize: '14px'
                                }}
                            />
                        </div>
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                                <label style={{
                                    color: '#e1e5e9',
                                    fontSize: '14px',
                                    fontWeight: '500'
                                }}>
                                    API Secret
                                </label>
                                <button
                                    type="button"
                                    onClick={() => setShowSecret(!showSecret)}
                                    style={{
                                        background: 'none',
                                        border: 'none',
                                        color: '#787b86',
                                        fontSize: '11px',
                                        textDecoration: 'underline',
                                        cursor: 'pointer'
                                    }}
                                >
                                    {showSecret ? "Hide" : "Show"}
                                </button>
                            </div>
                            <input
                                type={showSecret ? "text" : "password"}
                                value={apiSecret}
                                onChange={(e) => setApiSecret(e.target.value)}
                                placeholder="cs_..."
                                required
                                style={{
                                    width: '100%',
                                    padding: '8px 12px',
                                    backgroundColor: '#1e222d',
                                    border: '1px solid #363a45',
                                    borderRadius: '4px',
                                    color: '#e1e5e9',
                                    fontSize: '14px'
                                }}
                            />
                        </div>
                        {error && <div style={{ color: '#ff5b5b', fontSize: '12px' }}>{error}</div>}
                        <div style={{ display: 'flex', gap: '8px', paddingTop: '8px' }}>
                            <button type="submit" className="btn primary" style={{ flex: 1 }}>
                                Save & Continue
                            </button>
                            <button type="button" className="btn" onClick={onClear}>
                                Clear
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    )
}