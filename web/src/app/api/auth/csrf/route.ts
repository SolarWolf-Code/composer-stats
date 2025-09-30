import { NextResponse } from "next/server";
import { getCsrfToken } from "@/lib/csrf";

/**
 * GET endpoint to retrieve CSRF token
 * Token is generated and stored in session, then returned to client
 * Client must include this token in all state-changing requests
 */
export async function GET() {
    try {
        const token = await getCsrfToken();

        return NextResponse.json({
            csrfToken: token
        });
    } catch (error) {
        console.error("Failed to get CSRF token:", error);
        return NextResponse.json(
            { error: "Failed to get CSRF token" },
            { status: 500 }
        );
    }
}
