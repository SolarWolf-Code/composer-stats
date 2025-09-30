import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/session";
import { randomBytes } from "crypto";

/**
 * CSRF Protection using Synchronizer Token Pattern (OWASP Recommended)
 * 
 * This implementation follows OWASP's primary recommendation:
 * - Token is generated and stored in the session (server-side)
 * - Token is sent to client and included in requests
 * - Server validates token matches session token
 * - Resistant to subdomain attacks (unlike double-submit cookie)
 * 
 * Reference: https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html
 */

const CSRF_HEADER_NAME = "x-csrf-token";
const SAFE_METHODS = ["GET", "HEAD", "OPTIONS"];

/**
 * Generate a cryptographically secure random CSRF token
 */
export function generateCsrfToken(): string {
    return randomBytes(32).toString("base64url");
}

/**
 * Get or create CSRF token for the session
 */
export async function getCsrfToken(): Promise<string> {
    const session = await getSession();

    // Generate new token if one doesn't exist
    if (!session.csrfToken) {
        session.csrfToken = generateCsrfToken();
        await session.save();
    }

    return session.csrfToken;
}

/**
 * Validate CSRF token from request against session token
 * Returns NextResponse with error if validation fails, null if valid
 */
export async function validateCsrfToken(request: NextRequest): Promise<NextResponse | null> {
    const method = request.method.toUpperCase();

    // Skip validation for safe methods
    if (SAFE_METHODS.includes(method)) {
        return null;
    }

    try {
        // Get session token
        const session = await getSession();
        const sessionToken = session.csrfToken;

        if (!sessionToken) {
            return NextResponse.json(
                { error: "CSRF token not found in session. Please refresh and try again." },
                { status: 403 }
            );
        }

        // Get token from request header
        const requestToken = request.headers.get(CSRF_HEADER_NAME);

        if (!requestToken) {
            return NextResponse.json(
                { error: "CSRF token missing from request" },
                { status: 403 }
            );
        }

        // Constant-time comparison to prevent timing attacks
        if (!timingSafeEqual(sessionToken, requestToken)) {
            return NextResponse.json(
                { error: "Invalid CSRF token" },
                { status: 403 }
            );
        }

        // Token is valid
        return null;
    } catch (error) {
        console.error("CSRF validation error:", error);
        return NextResponse.json(
            { error: "CSRF validation failed" },
            { status: 500 }
        );
    }
}

/**
 * Timing-safe string comparison to prevent timing attacks
 */
function timingSafeEqual(a: string, b: string): boolean {
    if (a.length !== b.length) {
        return false;
    }

    let result = 0;
    for (let i = 0; i < a.length; i++) {
        result |= a.charCodeAt(i) ^ b.charCodeAt(i);
    }

    return result === 0;
}

/**
 * Regenerate CSRF token (call after login/privilege escalation)
 */
export async function regenerateCsrfToken(): Promise<string> {
    const session = await getSession();
    session.csrfToken = generateCsrfToken();
    await session.save();
    return session.csrfToken;
}
