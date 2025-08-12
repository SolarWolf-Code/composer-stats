"use client"

import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Button } from "@/components/ui/button"

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
        <div className="min-h-dvh w-full flex items-center justify-center p-4">
            <Card className="w-full max-w-sm">
                <CardHeader>
                    <CardTitle className="text-lg">Sign in to Composer Stats</CardTitle>
                    <p className="text-xs text-muted-foreground">Enter your API credentials. They are stored only in your browser and used per request.</p>
                </CardHeader>
                <CardContent>
                    <form onSubmit={onSubmit} className="space-y-3">
                        <div className="space-y-1.5">
                            <Label htmlFor="apiKeyId">API Key ID</Label>
                            <Input
                                id="apiKeyId"
                                value={apiKeyId}
                                onChange={(e) => setApiKeyId(e.target.value)}
                                placeholder="ck_..."
                                required
                                autoFocus
                            />
                        </div>
                        <div className="space-y-1.5">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="apiSecret">API Secret</Label>
                                <button
                                    type="button"
                                    className="text-[11px] underline text-muted-foreground"
                                    onClick={() => setShowSecret((s) => !s)}
                                >
                                    {showSecret ? "Hide" : "Show"}
                                </button>
                            </div>
                            <Input
                                id="apiSecret"
                                value={apiSecret}
                                onChange={(e) => setApiSecret(e.target.value)}
                                placeholder="cs_..."
                                type={showSecret ? "text" : "password"}
                                required
                            />
                        </div>
                        {error && <div className="text-xs text-red-500">{error}</div>}
                        <div className="flex items-center gap-2 pt-1">
                            <Button type="submit" className="flex-1">Save & Continue</Button>
                            <Button type="button" variant="secondary" onClick={onClear}>Clear</Button>
                        </div>
                    </form>
                </CardContent>
            </Card>
        </div>
    )
}


