import { getIronSession, IronSession, SessionOptions } from "iron-session";
import { cookies } from "next/headers";

export interface SessionData {
    apiKeyId?: string;
    apiSecret?: string;
    isLoggedIn: boolean;
    csrfToken?: string;
}

export const sessionOptions: SessionOptions = {
    password: process.env.SESSION_SECRET || "complex_password_at_least_32_characters_long_change_in_production",
    cookieName: "composer_stats_session",
    cookieOptions: {
        secure: process.env.NODE_ENV === "production",
        httpOnly: true,
        sameSite: "strict", // Strict mode since we have CSRF token protection
        maxAge: 60 * 60 * 24 * 7, // 7 days
    },
};

export async function getSession(): Promise<IronSession<SessionData>> {
    const cookieStore = await cookies();
    return getIronSession<SessionData>(cookieStore, sessionOptions);
}

