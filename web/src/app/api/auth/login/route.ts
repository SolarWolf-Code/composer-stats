import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";

export async function POST(request: NextRequest) {
    try {
        const body = await request.json();
        const { apiKeyId, apiSecret } = body;

        if (!apiKeyId || !apiSecret) {
            return NextResponse.json(
                { error: "API Key ID and Secret are required" },
                { status: 400 }
            );
        }

        // Get session and save credentials
        const session = await getSession();
        session.apiKeyId = apiKeyId;
        session.apiSecret = apiSecret;
        session.isLoggedIn = true;
        await session.save();

        return NextResponse.json({ success: true });
    } catch (error) {
        console.error("Login error:", error);
        return NextResponse.json(
            { error: "Failed to save credentials" },
            { status: 500 }
        );
    }
}

