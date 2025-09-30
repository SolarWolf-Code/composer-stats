import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { validateCsrfToken } from "@/lib/csrf";

export async function POST(request: NextRequest) {
    // CSRF protection
    const csrfError = await validateCsrfToken(request);
    if (csrfError) return csrfError;

    try {
        const session = await getSession();
        session.destroy();
        return NextResponse.json({ success: true });
    } catch (error) {
        console.error("Logout error:", error);
        return NextResponse.json(
            { error: "Failed to logout" },
            { status: 500 }
        );
    }
}

