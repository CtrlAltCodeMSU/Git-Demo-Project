/** @odoo-module **/
/** 
import { session } from "@web/session";
import { registry } from "@web/core/registry";

// --- Countdown Modal UI ---
const createCountdownModal = () => {
    const overlay = document.createElement("div");
    overlay.id = "idle-timeout-overlay";
    Object.assign(overlay.style, {
        position: "fixed",
        inset: "0",
        backgroundColor: "rgba(0, 0, 0, 0.55)",
        zIndex: "99999",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "sans-serif",
    });

    const modal = document.createElement("div");
    Object.assign(modal.style, {
        backgroundColor: "#fff",
        borderRadius: "12px",
        padding: "40px 48px",
        textAlign: "center",
        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
        minWidth: "340px",
        maxWidth: "90vw",
    });

    const icon = document.createElement("div");
    icon.innerHTML = "⏱️";
    Object.assign(icon.style, { fontSize: "48px", marginBottom: "12px" });

    const title = document.createElement("h2");
    title.innerText = "Session Expiring Soon";
    Object.assign(title.style, {
        margin: "0 0 8px",
        fontSize: "20px",
        color: "#333",
    });

    const message = document.createElement("p");
    message.innerText = "You have been inactive. Your session will expire in:";
    Object.assign(message.style, {
        margin: "0 0 16px",
        fontSize: "14px",
        color: "#666",
    });

    const countdown = document.createElement("div");
    countdown.id = "idle-countdown-number";
    Object.assign(countdown.style, {
        fontSize: "56px",
        fontWeight: "bold",
        color: "#e74c3c",
        lineHeight: "1",
        marginBottom: "24px",
    });
    countdown.innerText = "10";

    const stayBtn = document.createElement("button");
    stayBtn.id = "idle-stay-btn";
    stayBtn.innerText = "Stay Logged In";
    Object.assign(stayBtn.style, {
        backgroundColor: "#875A7B",
        color: "#fff",
        border: "none",
        borderRadius: "6px",
        padding: "10px 28px",
        fontSize: "15px",
        cursor: "pointer",
        marginRight: "12px",
    });

    const logoutBtn = document.createElement("button");
    logoutBtn.id = "idle-logout-btn";
    logoutBtn.innerText = "Logout Now";
    Object.assign(logoutBtn.style, {
        backgroundColor: "#fff",
        color: "#e74c3c",
        border: "2px solid #e74c3c",
        borderRadius: "6px",
        padding: "10px 28px",
        fontSize: "15px",
        cursor: "pointer",
    });

    modal.appendChild(icon);
    modal.appendChild(title);
    modal.appendChild(message);
    modal.appendChild(countdown);
    modal.appendChild(stayBtn);
    modal.appendChild(logoutBtn);
    overlay.appendChild(modal);

    return overlay;
};

export const idleTimeoutService = {
    dependencies: ["orm"],

    async start(env, { orm }) {

        // --- Resolve User ID ---
        let userId = session.uid;

        if (!userId) {
            try {
                const response = await fetch("/web/session/get_session_info", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }),
                });
                const data = await response.json();
                userId = data?.result?.uid;
                console.log("Idle Timeout: userId from RPC →", userId);
            } catch (e) {
                console.error("Idle Timeout: Could not resolve user ID.", e);
            }
        }

        if (!userId || session.is_public) {
            console.warn("Idle Timeout: No valid user session. Skipping.");
            return;
        }

        try {
            const res = await orm.read(
                "res.users",
                [userId],
                ["idle_timeout", "custom_idle_timeout"]
            );

            if (!res || res.length === 0) return;

            const userData = res[0];
            let minutes = 0;

            if (!userData.idle_timeout || userData.idle_timeout === "never") {
                console.log("Idle Timeout: Set to 'Never'. Monitoring disabled.");
                return;
            } else if (userData.idle_timeout === "custom") {
                minutes = userData.custom_idle_timeout || 0;
            } else {
                minutes = parseInt(userData.idle_timeout, 10);
            }

            if (minutes <= 0) {
                console.warn("Idle Timeout: Invalid minutes value:", minutes);
                return;
            }

            const timeoutMs = minutes * 60 * 1000;
            const countdownSeconds = 10;

            let idleTimer = null;
            let countdownInterval = null;
            let modalVisible = false;

            const events = [
                "mousedown", "mousemove", "keydown",
                "scroll", "touchstart", "click", "wheel",
            ];

            const doLogout = () => {
                const overlay = document.getElementById("idle-timeout-overlay");
                if (overlay) overlay.remove();
                window.location.href = "/web/session/logout";
            };

            const dismissModal = () => {
                clearInterval(countdownInterval);
                countdownInterval = null;
                const overlay = document.getElementById("idle-timeout-overlay");
                if (overlay) overlay.remove();
                modalVisible = false;
                // Re-attach listeners
                events.forEach((name) =>
                    document.addEventListener(name, onActivity, true)
                );
            };

            const showCountdownModal = () => {
                if (modalVisible) return;
                modalVisible = true;

                // Detach activity listeners while modal is open
                events.forEach((name) =>
                    document.removeEventListener(name, onActivity, true)
                );

                const overlay = createCountdownModal();
                document.body.appendChild(overlay);

                let remaining = countdownSeconds;
                const countdownEl = document.getElementById("idle-countdown-number");
                const stayBtn = document.getElementById("idle-stay-btn");
                const logoutBtn = document.getElementById("idle-logout-btn");

                countdownInterval = setInterval(() => {
                    remaining -= 1;
                    if (countdownEl) {
                        countdownEl.innerText = remaining;
                        if (remaining <= 5) {
                            countdownEl.style.color = "#c0392b";
                        }
                    }
                    if (remaining <= 0) {
                        clearInterval(countdownInterval);
                        doLogout();
                    }
                }, 1000);

                stayBtn.addEventListener("click", () => {
                    dismissModal();
                    resetTimer();
                });

                logoutBtn.addEventListener("click", () => {
                    clearInterval(countdownInterval);
                    doLogout();
                });
            };

            const onActivity = () => {
                if (modalVisible) return;
                resetTimer();
            };

            const resetTimer = () => {
                if (idleTimer) clearTimeout(idleTimer);
                // Use native setTimeout — no import needed
                idleTimer = setTimeout(showCountdownModal, timeoutMs);
            };

            events.forEach((name) => {
                document.addEventListener(name, onActivity, true);
            });

            resetTimer();
            console.log(`Idle Timeout: Active. Warning modal after ${minutes} min of inactivity.`);

        } catch (e) {
            console.error("Idle Timeout: Critical failure.", e);
        }
    },
};

registry.category("services").add("idleTimeout", idleTimeoutService);

**/

/** @odoo-module **/
import { session } from "@web/session";
import { registry } from "@web/core/registry";

// --- Countdown Modal UI ---
const createCountdownModal = () => {
    const overlay = document.createElement("div");
    overlay.id = "idle-timeout-overlay";
    Object.assign(overlay.style, {
        position: "fixed",
        inset: "0",
        backgroundColor: "rgba(0, 0, 0, 0.55)",
        zIndex: "99999",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "sans-serif",
    });

    const modal = document.createElement("div");
    Object.assign(modal.style, {
        backgroundColor: "#fff",
        borderRadius: "12px",
        padding: "40px 48px",
        textAlign: "center",
        boxShadow: "0 8px 32px rgba(0,0,0,0.25)",
        minWidth: "340px",
        maxWidth: "90vw",
    });

    const icon = document.createElement("div");
    icon.innerHTML = "⏱️";
    Object.assign(icon.style, { fontSize: "48px", marginBottom: "12px" });

    const title = document.createElement("h2");
    title.innerText = "Session Expiring Soon";
    Object.assign(title.style, { margin: "0 0 8px", fontSize: "20px", color: "#333" });

    const message = document.createElement("p");
    message.innerText = "You have been inactive. Your session will expire in:";
    Object.assign(message.style, { margin: "0 0 16px", fontSize: "14px", color: "#666" });

    const countdown = document.createElement("div");
    countdown.id = "idle-countdown-number";
    Object.assign(countdown.style, {
        fontSize: "56px",
        fontWeight: "bold",
        color: "#e74c3c",
        lineHeight: "1",
        marginBottom: "24px",
    });
    countdown.innerText = "10";

    const stayBtn = document.createElement("button");
    stayBtn.id = "idle-stay-btn";
    stayBtn.innerText = "Stay Logged In";
    Object.assign(stayBtn.style, {
        backgroundColor: "#875A7B",
        color: "#fff",
        border: "none",
        borderRadius: "6px",
        padding: "10px 28px",
        fontSize: "15px",
        cursor: "pointer",
        marginRight: "12px",
    });
// logouot button added 
    const logoutBtn = document.createElement("button");
    logoutBtn.id = "idle-logout-btn";
    logoutBtn.innerText = "Logout Now";
    Object.assign(logoutBtn.style, {
        backgroundColor: "#fff",
        color: "#e74c3c",
        border: "2px solid #e74c3c",
        borderRadius: "6px",
        padding: "10px 28px",
        fontSize: "15px",
        cursor: "pointer",
    });

    modal.appendChild(icon);
    modal.appendChild(title);
    modal.appendChild(message);
    modal.appendChild(countdown);
    modal.appendChild(stayBtn);
    modal.appendChild(logoutBtn);
    overlay.appendChild(modal);

    return overlay;
};

export const idleTimeoutService = {
    dependencies: ["orm"],

    async start(env, { orm }) {

        // --- Resolve User ID ---
        let userId = session.uid;

        if (!userId) {
            try {
                const response = await fetch("/web/session/get_session_info", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ jsonrpc: "2.0", method: "call", params: {} }),
                });
                const data = await response.json();
                userId = data?.result?.uid;
            } catch (e) {
                console.error("Idle Timeout: Could not resolve user ID.", e);
            }
        }

        if (!userId || session.is_public) {
            console.warn("Idle Timeout: No valid user session. Skipping.");
            return;
        }

        try {
            const res = await orm.read(
                "res.users",
                [userId],
                ["idle_timeout", "custom_idle_timeout"]
            );

            if (!res || res.length === 0) return;

            const userData = res[0];
            let minutes = 0;

            if (!userData.idle_timeout || userData.idle_timeout === "never") {
                console.log("Idle Timeout: Set to 'Never'. Monitoring disabled.");
                return;
            } else if (userData.idle_timeout === "custom") {
                minutes = userData.custom_idle_timeout || 0;
            } else {
                minutes = parseInt(userData.idle_timeout, 10);
            }

            if (minutes <= 0) {
                console.warn("Idle Timeout: Invalid minutes value:", minutes);
                return;
            }

            const timeoutMs = minutes * 60 * 1000;
            const countdownMs = 10 * 1000; // 10 seconds in ms

            let idleTimer = null;
            let countdownInterval = null;
            let modalVisible = false;

            // --- KEY FIX: Track timestamps instead of relying on timer accuracy ---
            let lastActivityTime = Date.now();
            let countdownStartTime = null;

            const events = [
                "mousedown", "mousemove", "keydown",
                "scroll", "touchstart", "click", "wheel",
            ];

            const doLogout = () => {
                const overlay = document.getElementById("idle-timeout-overlay");
                if (overlay) overlay.remove();
                window.location.href = "/web/session/logout";
            };

            const dismissModal = () => {
                clearInterval(countdownInterval);
                countdownInterval = null;
                countdownStartTime = null;
                const overlay = document.getElementById("idle-timeout-overlay");
                if (overlay) overlay.remove();
                modalVisible = false;
                events.forEach((name) =>
                    document.addEventListener(name, onActivity, true)
                );
            };

            const showCountdownModal = () => {
                if (modalVisible) return;
                modalVisible = true;
                countdownStartTime = Date.now();

                events.forEach((name) =>
                    document.removeEventListener(name, onActivity, true)
                );

                const overlay = createCountdownModal();
                document.body.appendChild(overlay);

                const countdownEl = document.getElementById("idle-countdown-number");
                const stayBtn = document.getElementById("idle-stay-btn");
                const logoutBtn = document.getElementById("idle-logout-btn");

                // --- Timestamp-based countdown tick ---
                const tick = () => {
                    const elapsed = Date.now() - countdownStartTime;
                    const remaining = Math.ceil((countdownMs - elapsed) / 1000);

                    if (countdownEl) {
                        // Clamp display between 0 and 10
                        countdownEl.innerText = Math.max(0, remaining);
                        countdownEl.style.color = remaining <= 5 ? "#c0392b" : "#e74c3c";
                    }

                    if (elapsed >= countdownMs) {
                        clearInterval(countdownInterval);
                        doLogout();
                    }
                };

                // Run tick immediately so display is correct on tab focus
                tick();
                countdownInterval = setInterval(tick, 500); // 500ms for responsiveness

                stayBtn.addEventListener("click", () => {
                    dismissModal();
                    resetTimer();
                });

                logoutBtn.addEventListener("click", () => {
                    clearInterval(countdownInterval);
                    doLogout();
                });
            };

            // --- Page Visibility API: handles background tab accurately ---
            document.addEventListener("visibilitychange", () => {
                if (document.visibilityState === "visible") {
                    const now = Date.now();

                    if (modalVisible && countdownStartTime) {
                        // Check if countdown has already expired while tab was hidden
                        const elapsed = now - countdownStartTime;
                        if (elapsed >= countdownMs) {
                            clearInterval(countdownInterval);
                            doLogout();
                            return;
                        }
                        // Otherwise let the interval tick correct itself immediately
                        return;
                    }

                    // Check if idle threshold was crossed while tab was hidden
                    const idleElapsed = now - lastActivityTime;
                    if (idleElapsed >= timeoutMs) {
                        // Show modal or logout immediately
                        if (idleElapsed >= timeoutMs + countdownMs) {
                            // Both idle + countdown periods have passed — logout immediately
                            doLogout();
                        } else {
                            // Idle period passed but still within countdown window
                            // Show modal with correct remaining countdown time
                            if (!modalVisible) {
                                showCountdownModal();
                                // Adjust countdownStartTime to reflect actual elapsed time
                                const countdownElapsed = idleElapsed - timeoutMs;
                                countdownStartTime = now - countdownElapsed;
                            }
                        }
                    }
                }
            });

            const onActivity = () => {
                if (modalVisible) return;
                lastActivityTime = Date.now(); // Timestamp updated on every activity
                resetTimer();
            };

            const resetTimer = () => {
                if (idleTimer) clearTimeout(idleTimer);
                idleTimer = setTimeout(showCountdownModal, timeoutMs);
            };

            events.forEach((name) => {
                document.addEventListener(name, onActivity, true);
            });

            resetTimer();
            console.log(`Idle Timeout: Active. Logout after ${minutes} min of inactivity.`);

        } catch (e) {
            console.error("Idle Timeout: Critical failure.", e);
        }
    },
};

registry.category("services").add("idleTimeout", idleTimeoutService);