import { NextResponse } from "next/server";
import { getSession } from "@/lib/session";

export async function GET() {
    try {
        const session = await getSession();

        if (!session.isLoggedIn || !session.apiKeyId || !session.apiSecret) {
            return NextResponse.json({ isLoggedIn: false }, { status: 401 });
        }

        return NextResponse.json({ isLoggedIn: true });
    } catch (error) {
        console.error("Session check error:", error);
        return NextResponse.json({ isLoggedIn: false }, { status: 500 });
    }
}

